# -*- coding: utf-8 -*-

# (C) Copyright 2020, 2021, 2022, 2023, 2024 IBM. All Rights Reserved.
#
# Licensed under the MIT license. See LICENSE file in the project root for details.

"""Tests for continuing to train."""

from typing import Union

from pytest import mark
from torch import allclose, manual_seed, mean, rand, tensor
from torch.nn import Linear

from aihwkit.optim.analog_optimizer import AnalogSGD
from aihwkit.simulator.configs import QuantizedTorchInferenceRPUConfig, TorchInferenceRPUConfig
from aihwkit.simulator.configs.utils import BoundManagementType, NoiseManagementType
from aihwkit.nn.conversion import convert_to_analog


def train_linear_regression(
    rpu_cls: Union[TorchInferenceRPUConfig, QuantizedTorchInferenceRPUConfig], reload: bool
):
    """Train a linear regression model and return the losses."""

    def generate_toy_data(num_samples=100):
        manual_seed(0)
        x = 2 * rand(num_samples, 1)
        y = 4 + 3 * x + rand(num_samples, 1)
        return x, y

    def mean_squared_error(y_true, y_pred):
        return mean((y_true - y_pred) ** 2)

    manual_seed(0)
    learning_rate = 0.001
    x, y = generate_toy_data()
    model = Linear(1, 1)

    rpu_config = rpu_cls()
    rpu_config.forward.bound_management = BoundManagementType.NONE
    rpu_config.forward.noise_management = NoiseManagementType.NONE
    rpu_config.forward.out_noise = 0.0
    rpu_config.pre_post.input_range.enable = True
    rpu_config.pre_post.input_range.init_value = 3.0
    rpu_config.forward.is_perfect = True
    rpu_config.pre_post.input_range.enable = True
    rpu_config.pre_post.input_range.init_from_data = 1000
    rpu_config.pre_post.input_range.learn_input_range = False
    rpu_config.pre_post.input_range.decay = 0.0

    model = convert_to_analog(model, rpu_config)
    optimizer = AnalogSGD(params=model.parameters(), lr=learning_rate)

    losses = []
    for epoch in range(1000):
        loss = mean_squared_error(y, model.forward(x))
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        losses.append(loss.item())

        if epoch == 500 and reload:
            state_dict = model.state_dict()
            optimizer_sd = optimizer.state_dict()
            model = Linear(1, 1)
            model = convert_to_analog(model, rpu_config)
            optimizer = AnalogSGD(params=model.parameters(), lr=learning_rate)
            model.load_state_dict(state_dict)
            optimizer.load_state_dict(optimizer_sd)
    return tensor(losses)


@mark.parametrize("rpu_cls", [TorchInferenceRPUConfig, QuantizedTorchInferenceRPUConfig])
def test_continue_training(rpu_cls):
    """Test if continuing to train still works."""
    losses_false = train_linear_regression(rpu_cls, reload=False)
    losses_true = train_linear_regression(rpu_cls, reload=True)
    assert allclose(losses_false, losses_true, atol=1e-4)
