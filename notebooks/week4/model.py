import tensorflow as tf
from ops import * 

class DCGAN(object):
    """Deep Convolutional Generative Adversarial Network
    
    Construct discriminator and generator to prepare for training.
    """
    
    def __init__(self, batch_size=100, learning_rate=0.0002, image_size=64, output_size=64, 
                 dim_color=3, dim_z=100, dim_df=64, dim_gf=64):
        """
        Args:
            learning_rate: (optional) learning rate for discriminator and generator
            image_size: (optional) spatial size of input image for discriminator
            output_size: (optional) spatial size of image generated by generator
            dim_color: (optional) dimension of image color; default is 3 for rgb
            dim_z: (optional) dimension of z (random input vector for generator)
            dim_df: (optional) dimension of discriminator's filter in first convolution layer
            dim_gf: (optional) dimension of generator's filter in last convolution layer
        """
        # hyper parameters
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.image_size = image_size
        self.output_size = output_size
        self.dim_color = dim_color
        self.dim_z = dim_z
        self.dim_df = dim_df
        self.dim_gf = dim_gf
        
        # placeholder
        self.images = tf.placeholder(tf.float32, shape=[batch_size, image_size, image_size, dim_color], name='images')
        self.z = tf.placeholder(tf.float32, shape=[None, dim_z], name='input_for_generator')
        
        # batch normalization layer for discriminator and generator
        self.d_bn1 = batch_norm(name='d_bn1')
        self.d_bn2 = batch_norm(name='d_bn2')
        self.d_bn3 = batch_norm(name='d_bn3')
        
        self.g_bn1 = batch_norm(name='g_bn1')
        self.g_bn2 = batch_norm(name='g_bn2')
        self.g_bn3 = batch_norm(name='g_bn3')
        self.g_bn4 = batch_norm(name='g_bn4')
        
        
    def build_model(self):
        
        # construct generator and discriminator for training phase 
        self.fake_images = self.generator(self.z)                              # (batch_size, 64, 64, 3)
        self.logits_real = self.discriminator(self.images)                     # (batch_size,)
        self.logits_fake = self.discriminator(self.fake_images, reuse=True)    # (batch_size,)
        
        # construct generator for test phase
        self.sampled_images = self.generator(self.z, reuse=True)               # (batch_size, 64, 64, 3)
        
        # compute loss 
        self.d_loss_real = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(self.logits_real, tf.ones_like(self.logits_real)))
        self.d_loss_fake = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(self.logits_fake, tf.zeros_like(self.logits_fake)))           
        self.d_loss = self.d_loss_real + self.d_loss_fake
        self.g_loss = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(self.logits_fake, tf.ones_like(self.logits_fake)))
        
        # divide variables for discriminator and generator 
        t_vars = tf.trainable_variables()
        self.d_vars = [var for var in t_vars if 'discriminator' in var.name]
        self.g_vars = [var for var in t_vars if 'generator' in var.name]
        
        # optimizer for discriminator and generator
        with tf.name_scope('optimizer'):
            self.d_optimizer = tf.train.AdamOptimizer(learning_rate=self.learning_rate, beta1=0.5).minimize(self.d_loss, var_list=self.d_vars)
            self.g_optimizer = tf.train.AdamOptimizer(learning_rate=self.learning_rate, beta1=0.5).minimize(self.g_loss, var_list=self.g_vars)                  
        
        # summary ops for tensorboard visualization
        tf.scalar_summary('d_loss_real', self.d_loss_real)
        tf.scalar_summary('d_loss_fake', self.d_loss_fake)
        tf.scalar_summary('d_loss', self.d_loss)
        tf.scalar_summary('g_loss', self.g_loss)
        tf.image_summary('sampled_images', self.sampled_images)
        
        for var in tf.trainable_variables():
            tf.histogram_summary(var.op.name, var)
            
        self.summary_op = tf.merge_all_summaries() 
        
        self.saver = tf.train.Saver()
            
            
    def generator(self, z, reuse=False):
        """Generator: Deconvolutional neural network with relu activations.
        
        Last deconv layer does not use batch normalization.
        
        Args:
            z: random input vectors, of shape (batch_size, dim_z)
            
        Returns:
            out: generated images, of shape (batch_size, image_size, image_size, dim_color)
        """
        if reuse:
            train = False
        else:
            train = True
        
        with tf.variable_scope('generator', reuse=reuse):
            
            # spatial size for convolution
            s = self.output_size
            s2, s4, s8, s16 = s/2, s/4, s/8, s/16     # 32, 16, 8, 4
            
            # project and reshape z 
            h1= linear(z, s16*s16*self.dim_gf*8, name='g_h1')     # (batch_size, 4*4*512)
            h1 = tf.reshape(h1, [-1, s16, s16, self.dim_gf*8])    # (batch_size, 4, 4, 512) 
            h1 = relu(self.g_bn1(h1, train=train))
            
            h2 = deconv2d(h1, [self.batch_size, s8, s8, self.dim_gf*4], name='g_h2')   # (batch_size, 8, 8, 256)
            h2 = relu(self.g_bn2(h2, train=train))
            
            h3 = deconv2d(h2, [self.batch_size, s4, s4, self.dim_gf*2], name='g_h3')   # (batch_size, 16, 16, 128)
            h3 = relu(self.g_bn3(h3, train=train))
            
            h4 = deconv2d(h3, [self.batch_size, s2, s2, self.dim_gf], name='g_h4')     # (batch_size, 32, 32, 64)
            h4 = relu(self.g_bn4(h4, train=train))
            
            out = deconv2d(h4, [self.batch_size, s, s, self.dim_color], name='g_out')  # (batch_size, 64, 64, dim_color)
            
            return tf.nn.tanh(out)
    
    
    def discriminator(self, images, reuse=False):
        """Discrimator: Convolutional neural network with leaky relu activations.
        
        First conv layer does not use batch normalization.
        
        Args: 
            images: real or fake images of shape (batch_size, image_size, image_size, dim_color)  
        
        Returns:
            out: scores for whether it is a real image or a fake image, of shape (batch_size,)
        """
        with tf.variable_scope('discriminator', reuse=reuse):
        
            # convolution layer
            h1 = lrelu(conv2d(images, self.dim_df, name='d_h1'))                  # (batch_size, 32, 32, 64)
            h2 = lrelu(self.d_bn1(conv2d(h1, self.dim_df*2, name='d_h2')))        # (batch_size, 16, 16, 128)
            h3 = lrelu(self.d_bn2(conv2d(h2, self.dim_df*4, name='d_h3')))        # (batch_size, 8, 8, 256)
            h4 = lrelu(self.d_bn3(conv2d(h3, self.dim_df*8, name='d_h4')))        # (batch_size, 4, 4, 512)

            # fully connected layer
            h4 = tf.reshape(h4, [self.batch_size, -1])
            out = linear(h4, 1, name='d_out')                                     # (batch_size,)  

            return out