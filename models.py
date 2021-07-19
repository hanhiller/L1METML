from tensorflow.keras.models import Model
from tensorflow.keras.layers import Input, Dense, Embedding, BatchNormalization, Dropout, Lambda, Conv1D, SpatialDropout1D, Concatenate, Flatten, Reshape
import tensorflow.keras.backend as K
import tensorflow as tf
from tensorflow import slice
from tensorflow.keras import initializers
from weighted_sum_layer import weighted_sum_layer
import qkeras
from qkeras.qlayers import QDense, QActivation

def dense_embedding(n_features=6, n_features_cat=2, n_dense_layers=3, activation='relu', number_of_pupcandis=100, embedding_input_dim={0: 13, 1: 3}, emb_out_dim=8, with_bias=True, t_mode = 0):

    inputs_cont = Input(shape=(number_of_pupcandis, n_features), name='input')
    pxpy = Lambda(lambda x: slice(x, (0, 0, n_features-2), (-1, -1, -1)))(inputs_cont)

    embeddings = []
    for i_emb in range(n_features_cat):
        input_cat = Input(shape=(number_of_pupcandis, 1), name='input_cat{}'.format(i_emb))
        if i_emb == 0:
            inputs = [inputs_cont, input_cat]
        else:
            inputs.append(input_cat)
        embedding = Embedding(input_dim=embedding_input_dim[i_emb], output_dim=emb_out_dim, embeddings_initializer=initializers.RandomNormal(mean=0, stddev=0.4/emb_out_dim), name='embedding{}'.format(i_emb))(input_cat)
        embedding = Reshape((number_of_pupcandis, emb_out_dim))(embedding)
        embeddings.append(embedding)

    x = Concatenate()([inputs[0]] + [emb for emb in embeddings])

    for i_dense in range(n_dense_layers):
        x = Dense(8*2**(n_dense_layers-i_dense), activation = activation, kernel_initializer='lecun_uniform')(x)
        x = BatchNormalization(momentum=0.95)(x)

    if t_mode == 0:
        x = tf.keras.layers.GlobalAveragePooling1D(name='pool')(x)
        outputs = Dense(2, name = 'output', activation='linear')(x)

    if t_mode == 1:
        x = Dense(3 if with_bias else 1, activation='linear', kernel_initializer=initializers.VarianceScaling(scale=0.02))(x)
        x = Concatenate()([x, pxpy])
        x = weighted_sum_layer(with_bias, name="weighted_sum" if with_bias else "output")(x)

        if with_bias:
            x = Dense(2, name = 'output', activation='linear')(x)

        outputs = x

    keras_model = Model(inputs=inputs, outputs=outputs)

    return keras_model
    
def dense_embedding_quantized(n_features=6, n_features_cat=2, n_dense_layers=3, number_of_pupcandis=100, embedding_input_dim={0: 13, 1: 3}, emb_out_dim=8, with_bias=True, t_mode = 0, logit_total_bits=7, logit_int_bits=2, activation_total_bits=7, logit_quantizer = 'quantized_bits', activation_quantizer = 'quantized_relu', activation_int_bits=2, alpha=1, use_stochastic_rounding=False):

    
    logit_quantizer = getattr(qkeras.quantizers,logit_quantizer)(logit_total_bits, logit_int_bits, alpha=alpha, use_stochastic_rounding=use_stochastic_rounding)
    activation_quantizer = getattr(qkeras.quantizers,activation_quantizer)(activation_total_bits, activation_int_bits)
    
    inputs_cont = Input(shape=(number_of_pupcandis, n_features), name='input')
    pxpy = Lambda(lambda x: slice(x, (0, 0, n_features-2), (-1, -1, -1)))(inputs_cont)

    embeddings = []
    for i_emb in range(n_features_cat):
        input_cat = Input(shape=(number_of_pupcandis, 1), name='input_cat{}'.format(i_emb))
        if i_emb == 0:
            inputs = [inputs_cont, input_cat]
        else:
            inputs.append(input_cat)
        embedding = Embedding(input_dim=embedding_input_dim[i_emb], output_dim=emb_out_dim, embeddings_initializer=initializers.RandomNormal(mean=0, stddev=0.4/emb_out_dim), name='embedding{}'.format(i_emb))(input_cat)
        embedding = Reshape((number_of_pupcandis, emb_out_dim))(embedding)
        embeddings.append(embedding)

    x = Concatenate()([inputs[0]] + [emb for emb in embeddings])
    
    for i_dense in range(n_dense_layers):
        x = QDense(8*2**(n_dense_layers-i_dense), activation = activation_quantizer,kernel_quantizer=logit_quantizer, bias_quantizer=logit_quantizer, kernel_initializer='lecun_uniform')(x)
        x = BatchNormalization(momentum=0.95)(x)

    if t_mode == 0:
        x = qkeras.qpooling.QGlobalAveragePooling1D(name='pool', quantizer=logit_quantizer)(x)
        #pool size?
        outputs = QDense(2, name = 'output', bias_quantizer=logit_quantizer, kernel_quantizer=logit_quantizer, activation=activation_quantizer)(x)
        #similar to activation='linear'?

    if t_mode == 1:
        x = QDense(3 if with_bias else 1, activation=activation_quantizer, kernel_quantizer=logit_quantizer, bias_quantizer=logit_quantizer, kernel_initializer=initializers.VarianceScaling(scale=0.02))(x)
        x = Concatenate()([x, pxpy])
        x = weighted_sum_layer(with_bias, name="weighted_sum" if with_bias else "output")(x)

        if with_bias:
            x = QDense(2, name = 'output', bias_quantizer=logit_quantizer,kernel_quantizer=logit_quantizer, activation=activation_quantizer)(x)

        outputs = x

    keras_model = Model(inputs=inputs, outputs=outputs)

    return keras_model

# multiple values assigned to 'use_stochastic_rounding' in line 57 (activation quantizer), so i removed this argument
# QGlobalAveragePooling1D doesn't exist (line 80); only affects when mode 0 seleceted
