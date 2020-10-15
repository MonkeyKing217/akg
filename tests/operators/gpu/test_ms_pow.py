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
import numpy as np
from akg.ops.poly_gpu import pow_manual, pow_auto
from gen_random import random_gaussian
from akg.utils import kernel_exec as utils
from akg.utils.result_analysis import gpu_profiling
from akg.utils.format_transform import to_tvm_nd_array

def gen_data(shape1, shape2, in_dtype):
    support_list = {"float16": np.float16, "float32": np.float32}
    lhs = random_gaussian(shape1, miu=1, sigma=0.1).astype(support_list[in_dtype])
    rhs = random_gaussian(shape2, miu=1, sigma=0.1).astype(support_list[in_dtype])
    expect = np.power(lhs, rhs)
    output = np.full(expect.shape, np.nan, in_dtype)
    return lhs, rhs, output, expect

def test_ms_pow(shape1, shape2, in_dtype, poly_sch=False):
    if poly_sch:
        mod = utils.op_build_test(pow_auto, (shape1, shape2), (in_dtype, in_dtype), kernel_name="pow_auto", attrs={"target":"cuda"})
    else:
        mod = utils.op_build_test(pow_manual, (shape1, shape2), (in_dtype, in_dtype), kernel_name="pow_manual") 
    lhs, rhs, output, expect = gen_data(shape1, shape2, in_dtype)
    args = (lhs, rhs, output)
    output = utils.mod_launch(mod, args, expect=expect)
    res = np.allclose(output, expect, rtol=5e-03, atol=1.e-8)
    print("Test {}".format("Pass" if res else "Fail"))
    if not res:
        print("Error cuda:========================")
        print(mod.imported_modules[0].get_source())
        raise AssertionError("Test fail")
    lhs, rhs, expect = to_tvm_nd_array([lhs, rhs, expect])
    gpu_profiling(mod, lhs, rhs, expect, 400)
