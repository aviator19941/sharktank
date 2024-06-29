# Copyright 2024 Advanced Micro Devices, Inc
#
# Licensed under the Apache License v2.0 with LLVM Exceptions.
# See https://llvm.org/LICENSE.txt for license information.
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

import logging

logging.basicConfig(level=logging.DEBUG)

import unittest
from parameterized import parameterized

import torch

from shark_turbine import aot
from sharktank import kernels
from sharktank.ops.qconv_impls import _pad_last_2d


class conv_2d_nchw_fchw_test(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(42)

    @parameterized.expand(
        [
            (1e-3, 1e-5),
            (1e-3, 1e-5),
            (1e-3, 1e-5),
        ]
    )
    def testBS32(self, atol, rtol):
        dtype = torch.int8
        # inputs = (torch.rand([2,4,128,128]) * 64).to(dtype)
        inputs = (torch.rand([2, 320, 64, 64]) * 64).to(dtype)
        # padding = [1, 1]
        padding = [0, 0]
        extended_list = [item for item in padding for _ in range(2)]
        inputs_pad = _pad_last_2d(inputs, extended_list)
        weights = (torch.rand([640, 320, 1, 1]) * 64).to(dtype)
        bias = (torch.rand([640]) * 64).to(dtype)
        result = kernels.conv_2d_nchw_fchw(inputs_pad, weights, bias, [1, 1], [1, 1])

        # Tolerances are empirical and results are not expected to match exactly.
        ref = torch.nn.functional.conv2d(
            inputs, weights, bias=bias, stride=(1, 1), padding=(0, 0), dilation=(1, 1)
        )
        print(result.shape)
        print(ref.shape)
        torch.testing.assert_close(result, ref, atol=atol, rtol=rtol)

    def testExportStaticDims(self):
        class MyModule(torch.nn.Module):
            def forward(self, a, b, c):
                return kernels.conv_2d_nchw_fchw(a, b, c, [1, 1], [1, 1])

        mod = MyModule()
        dtype = torch.int8
        inputs = torch.rand([2, 320, 64, 64]) * 64
        padding = [1, 1]
        extended_list = [item for item in padding for _ in range(2)]
        inputs_pad = _pad_last_2d(inputs, extended_list)
        ep = torch.export.export(
            mod,
            args=(
                (inputs_pad).to(dtype),
                (torch.rand([640, 320, 3, 3]) * 64).to(dtype),
                (torch.rand([640]) * 64).to(dtype),
            ),
        )
        output = aot.export(ep)
        output.verify()
        asm = str(output.mlir_module)
        self.assertIn("@sharktank_conv_2d_nchw_fchw", asm)


if __name__ == "__main__":
    unittest.main()
