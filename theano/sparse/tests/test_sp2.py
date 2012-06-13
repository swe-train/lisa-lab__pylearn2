import time
import unittest

from nose.plugins.skip import SkipTest
import numpy as np
try:
    import scipy.sparse as sp
    import scipy.sparse
except ImportError:
    pass  # The variable enable_sparse will be used to disable the test file.

import theano

from theano import tensor as T
from theano import sparse as S
if not S.enable_sparse:
    raise SkipTest('Optional package sparse disabled')

from theano.sparse.sandbox import sp2 as S2

from theano.tests import unittest_tools as utt
from theano.sparse.basic import verify_grad_sparse


def as_sparse_format(data, format):
    if format == 'csc':
        return scipy.sparse.csc_matrix(data)
    elif format == 'csr':
        return scipy.sparse.csr_matrix(data)
    else:
        raise NotImplementedError()


def eval_outputs(outputs):
    return compile.function([], outputs)()[0]


def random_lil(shape, dtype, nnz):
    rval = sp.lil_matrix(shape, dtype=dtype)
    huge = 2 ** 30
    for k in range(nnz):
        # set non-zeros in random locations (row x, col y)
        idx = np.random.random_integers(huge, size=len(shape)) % shape
        value = np.random.rand()
        #if dtype *int*, value will always be zeros!
        if "int" in dtype:
            value = int(value * 100)
        rval.__setitem__(
                idx,
                value)
    return rval


class TestCast(utt.InferShapeTester):
    compatible_types = T.int_dtypes + T.continuous_dtypes
    x_csc = [S.csc_matrix(dtype=t) for t in compatible_types]
    x_csr = [S.csr_matrix(dtype=t) for t in compatible_types]

    indptr = np.array([0, 2, 3, 6])
    indices = np.array([0, 2, 2, 0, 1, 2])
    data = np.array([1, 2, 3, 4, 5, 6])
    properties = (data, indices, indptr)

    def setUp(self):
        super(TestCast, self).setUp()
        self.op_class = S2.Cast

    def test_cast(self):
        cast_csc = dict([
            (x, [theano.function([x], S2.Cast(t)(x))
                 for t in self.compatible_types])
            for x in self.x_csc])

        cast_csr = dict([
            (x, [theano.function([x], S2.Cast(t)(x))
                 for t in self.compatible_types])
            for x in self.x_csr])

        for x in self.x_csc:
            for f, t in zip(cast_csc[x], self.compatible_types):
                a = sp.csc_matrix(self.properties, dtype=x.dtype)
                assert f(a).dtype == t

        for x in self.x_csr:
            for f, t in zip(cast_csr[x], self.compatible_types):
                a = sp.csr_matrix(self.properties, dtype=x.dtype)
                assert f(a).dtype == t

    def test_infer_shape(self):
        for x in self.x_csc:
            for t in self.compatible_types:
                a = sp.csc_matrix(self.properties, dtype=x.dtype)
                self._compile_and_check([x],
                                        [S2.Cast(t)(x)],
                                        [a],
                                        self.op_class)

        for x in self.x_csr:
            for t in self.compatible_types:
                a = sp.csr_matrix(self.properties, dtype=x.dtype)
                self._compile_and_check([x],
                                        [S2.Cast(t)(x)],
                                        [a],
                                        self.op_class)

    def test_grad(self):
        for dtype in T.float_dtypes:
            a = sp.csc_matrix(self.properties, dtype=dtype)
            verify_grad_sparse(S2.Cast('float64'), [a])

        for dtype in T.float_dtypes:
            a = sp.csr_matrix(self.properties, dtype=dtype)
            verify_grad_sparse(S2.Cast('float64'), [a])


class EliminateZerosTester(utt.InferShapeTester):
    indptr = np.array([0, 2, 3, 6])
    indices = np.array([0, 2, 2, 0, 1, 2])
    data = np.array([1, 0, 3, 0, 5, 6], dtype='float32')
    properties = (data, indices, indptr)

    x_csc = S.csc_matrix('csc', dtype='float32')
    x_csr = S.csr_matrix('csr', dtype='float32')

    def setUp(self):
        super(EliminateZerosTester, self).setUp()
        self.op_class = S2.EliminateZeros

    def test_eliminate_zeros(self):
        f_csc = theano.function([self.x_csc], S2.eliminate_zeros(self.x_csc))
        f_csr = theano.function([self.x_csr], S2.eliminate_zeros(self.x_csr))

        a = sp.csc_matrix(self.properties, dtype='float32')
        b = a.copy()
        b.eliminate_zeros()
        assert np.all(f_csc(a).todense() == b.todense())

        a = sp.csr_matrix(self.properties)
        b = a.copy()
        b.eliminate_zeros()
        assert np.all(f_csr(a).todense() == b.todense())

    def test_infer_shape(self):
        a = sp.csc_matrix(self.properties, dtype='float32')
        self._compile_and_check([self.x_csc],
                                [S2.eliminate_zeros(self.x_csc)],
                                [a],
                                self.op_class)

        a = sp.csr_matrix(self.properties, dtype='float32')
        self._compile_and_check([self.x_csr],
                                [S2.eliminate_zeros(self.x_csr)],
                                [a],
                                self.op_class)

    def test_grad(self):
        a = sp.csc_matrix(self.properties, dtype='float32')
        verify_grad_sparse(S2.eliminate_zeros, [a])

        a = sp.csr_matrix(self.properties, dtype='float32')
        verify_grad_sparse(S2.eliminate_zeros, [a])


class test_structured_add_s_v(unittest.TestCase):
    def setUp(self):
        utt.seed_rng()

    def test_structured_add_s_v_grad(self):
        sp_types = {'csc': sp.csc_matrix,
            'csr': sp.csr_matrix}
        
        for format in ['csr', 'csc']:
            for dtype in ['float32', 'float64']:
                spmat = sp_types[format](random_lil((4, 3), dtype, 3))
                mat = np.asarray(np.random.rand(3), dtype=dtype)
                
                S.verify_grad_sparse(S2.structured_add_s_v,
                    [spmat, mat], structured=True)
    
    def test_structured_add_s_v(self):
        sp_types = {'csc': sp.csc_matrix,
            'csr': sp.csr_matrix}
        
        for format in ['csr', 'csc']:
            for dtype in ['float32', 'float64']:
                x = S.SparseType(format, dtype=dtype)()
                y = T.vector(dtype=dtype)
                f = theano.function([x, y], S2.structured_add_s_v(x, y))
                
                spmat = sp_types[format](random_lil((4, 3), dtype, 3))
                spones = spmat.copy()
                spones.data = np.ones_like(spones.data)
                mat = np.asarray(np.random.rand(3), dtype=dtype)
                
                out = f(spmat, mat)
                
                assert np.allclose(out.toarray(), spones.multiply(spmat + mat))


class test_mul_s_v(unittest.TestCase):
    def setUp(self):
        utt.seed_rng()

    def test_structured_add_s_v_grad(self):
        sp_types = {'csc': sp.csc_matrix,
            'csr': sp.csr_matrix}
        
        for format in ['csr', 'csc']:
            for dtype in ['float32', 'float64']:
                spmat = sp_types[format](random_lil((4, 3), dtype, 3))
                mat = np.asarray(np.random.rand(3), dtype=dtype)
                
                S.verify_grad_sparse(S2.mul_s_v,
                    [spmat, mat], structured=True)
    
    def test_mul_s_v(self):
        sp_types = {'csc': sp.csc_matrix,
            'csr': sp.csr_matrix}
        
        for format in ['csr', 'csc']:
            for dtype in ['float32', 'float64']:
                x = S.SparseType(format, dtype=dtype)()
                y = T.vector(dtype=dtype)
                f = theano.function([x, y], S2.mul_s_v(x, y))
                
                spmat = sp_types[format](random_lil((4, 3), dtype, 3))
                mat = np.asarray(np.random.rand(3), dtype=dtype)
                
                out = f(spmat, mat)
                
                assert np.allclose(out.toarray(), spmat.toarray() * mat)

if __name__ == '__main__':
    unittest.main()