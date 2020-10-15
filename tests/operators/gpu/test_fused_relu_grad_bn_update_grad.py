# Copyright 2020 Huawei Technologies Co., Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License

from __future__ import absolute_import
import numpy as np
from akg.utils import kernel_exec as utils
from gen_random import random_gaussian
from akg.utils.result_analysis import gpu_profiling
from akg.utils.format_transform import to_tvm_nd_array
from test_fused_pattern_grad import relu_grad_np, bn_beta_grad_np, bn_gamma_grad_np
from akg.ops.poly_gpu import fused_relu_grad_bn_update_grad_manual, fused_relu_grad_bn_update_grad_auto

def compute_expect(data_sum, in_bn, head_active, in_active, layout):
    out_dtype = data_sum.dtype
    relugrad = relu_grad_np(head_active, in_active).astype(out_dtype)
    inbn_cast = in_bn.astype(out_dtype)
    bn_beta_ad = bn_beta_grad_np(relugrad, layout)
    bn_gamma_ad = bn_gamma_grad_np(relugrad, inbn_cast, data_sum, layout)
    return [bn_gamma_ad, bn_beta_ad]


def gen_data(shape, out_shape, dtype, out_dtype, layout):
    support_list = {"float16": np.float16, "float32": np.float32}
    head = random_gaussian(shape, miu=1, sigma=0.1).astype(support_list[dtype])
    data_sum = random_gaussian(out_shape, miu=1, sigma=0.1).astype(support_list[out_dtype])
    in_bn = random_gaussian(shape, miu=1, sigma=0.1).astype(support_list[dtype])
    in_active = random_gaussian(shape, miu=1, sigma=0.1).astype(support_list[dtype])
    output = np.full(out_shape, np.nan, out_dtype)
    expect = compute_expect(data_sum, in_bn, head, in_active, layout)
    return head, data_sum, in_bn, in_active, output, expect

def test_fused_relu_grad_bn_update_grad(shape, out_shape, dtype="float16", layout="NHWC", out_dtype="float32", poly_sch=False):
    shape_list = [out_shape, shape, shape, shape]
    dtype_list = [out_dtype, dtype, dtype, dtype]
    op_attrs = [layout]
    if poly_sch:
        mod = utils.op_build_test(
            fused_relu_grad_bn_update_grad_auto,
            shape_list,
            dtype_list,
            op_attrs=op_attrs,
            kernel_name="fused_relu_grad_bn_update_grad_auto",
            attrs={
                "target": "cuda",
                "register_memory_depth":3})
    else:
        mod = utils.op_build_test(fused_relu_grad_bn_update_grad_manual, shape_list, dtype_list, kernel_name="fused_relu_grad_bn_update_grad_manual", op_attrs=op_attrs)
    
    head, data_sum, in_bn, in_active, output, expect = gen_data(shape, out_shape, dtype, out_dtype, layout)
    outputs = [output, output]
    inputs = [data_sum, in_bn, head, in_active]
    arg_list = inputs + outputs
    outputs = utils.mod_launch(mod, arg_list, outputs=tuple(range(-len(outputs), 0)), expect=expect)
    res = np.allclose(outputs, expect, rtol=5e-03, atol=1.e-8)
    print("Test {}".format("Pass" if res else "Fail"))
    if not res:
        print("Error cuda:========================")
        print(mod.imported_modules[0].get_source())
        raise AssertionError("Test fail")

    inputs = to_tvm_nd_array(inputs)
    expect = to_tvm_nd_array(expect)
    gpu_profiling(mod, *inputs, *expect, 400)
