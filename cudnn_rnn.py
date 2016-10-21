"""CUDNN RNN Test."""
import theano
import theano.tensor as T
from theano.gpuarray import dnn
from theano.gpuarray.type import gpuarray_shared_constructor
import numpy as np
import argparse
import time

mode_with_gpu = theano.compile.mode.get_default_mode().including('gpuarray').excluding('gpu')

parser = argparse.ArgumentParser()
parser.add_argument(
    "-n",
    "--network",
    help="network type rnn/lstm/gru",
    required=True
)
parser.add_argument(
    "-d",
    "--depth",
    help="num layers",
    type=int,
    required=True
)
parser.add_argument(
    "-b",
    "--batch_size",
    type=int,
    help="batch size",
    required=True
)
parser.add_argument(
    "-i",
    "--input",
    type=int,
    help="input dim",
    required=True
)
parser.add_argument(
    "-o",
    "--hidden",
    type=int,
    help="hidden dim",
    required=True
)
parser.add_argument(
    "-t",
    "--seq_len",
    type=int,
    help="time steps",
    required=True
)
args = parser.parse_args()
network_type = args.network
depth = args.depth
batch_size = args.batch_size
input_dim = args.input
hidden_dim = args.hidden
seq_len = args.seq_len
num_passes = 1000

x_val = np.random.random((seq_len, batch_size, input_dim)).astype(theano.config.floatX)
y_val = np.random.random((seq_len, batch_size, hidden_dim)).astype(theano.config.floatX)
h0_val = np.random.random((depth, batch_size, hidden_dim)).astype(theano.config.floatX)
c0_val = np.random.random((depth, batch_size, hidden_dim)).astype(theano.config.floatX)

start = time.time()

X = T.tensor3('X')
Y = T.tensor3('Y')
h0 = T.tensor3('h0')
c0 = T.tensor3('c0')

rnnb = dnn.RNNBlock(theano.config.floatX, hidden_dim, depth, 'lstm', input_mode='linear')
psize = rnnb.get_param_size([batch_size, input_dim])
params_cudnn = gpuarray_shared_constructor(
    np.zeros((psize,), dtype=theano.config.floatX))

# lstm = LSTM(input_dim, hidden_dim)
output = rnnb.apply(params_cudnn, X, h0, c0)[0]  # Only hidden states
cost = T.mean((Y - output) ** 2)
grads = T.grad(cost, params_cudnn)
cudnn_fn = theano.function(inputs=[X, h0, c0], outputs=output, mode=mode_with_gpu)
cudnn_grad_fn = theano.function(inputs=[X, Y, h0, c0], outputs=grads, mode=mode_with_gpu)

cudnn_out = cudnn_fn(x_val, h0_val, c0_val)
cudnn_grads = cudnn_grad_fn(x_val, y_val, h0_val, c0_val)

cudnn_grad_fn(x_val, y_val, h0_val, c0_val)
theano.sandbox.cuda.synchronize()
print "Setup : compile + forward/backward x 1"
print "--- %s seconds" % (time.time() - start)

num_processed = num_passes * batch_size
start = time.time()
for i in xrange(0, num_passes):
    cudnn_fn(x_val, h0_val, c0_val)
theano.sandbox.cuda.synchronize()
end = time.time()
print "Forward:"
print "--- %i samples in %s seconds (%f samples/s, %.7f s/sample) ---" % (num_processed, end - start, num_processed / (end - start), (end - start) / num_processed)

start = time.time()
for i in xrange(0, num_passes):
    cudnn_grad_fn(x_val, y_val, h0_val, c0_val)
theano.sandbox.cuda.synchronize()
end = time.time()
print "Forward + Backward:"
print "--- %i samples in %s seconds (%f samples/s, %.7f s/sample) ---" % (num_processed, end - start, num_processed / (end - start), (end - start) / num_processed)