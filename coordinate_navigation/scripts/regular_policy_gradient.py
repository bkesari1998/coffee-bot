'''
This class implements the Regular Policy Gradient algorithm to perform RL learning.
It takes in obs, and does a forward pass to get the action.
It does a backward pass when it receives a reward.

'''


# from typing import KeysView
import numpy as np
import time
import os
import math
#from chainer import cuda
# import pathlib

#import cupy as cp

#backend
#be = "gpu"
#device = 0


be = "cpu"

class RegularPolicyGradient(object):
    
    # constructor
    def __init__(self, num_actions, input_size, hidden_layer_size,
     learning_rate, gamma, decay_rate, greedy_e_epsilon, actions_id,
      episode_num, random_seed = 1, actions_to_be_bumped = None,
       guided_policy = None, exploration_mode = None, guided_action = None,
         load_model_flag = False, log_dir=None, failed_operator_name=None, trial_number=0):
        # store hyper-params
        self._A = num_actions
        self._D = input_size
        self._H = hidden_layer_size
        self._learning_rate = learning_rate
        self._decay_rate = decay_rate
        self._gamma = gamma
        
        # some temp variables
        self._xs,self._hs,self._dlogps,self._drs = [],[],[],[]

        self.init_model(random_seed)

        # variables governing exploration
        self._exploration = True # should be set to false when evaluating
        self._explore_eps = greedy_e_epsilon
        self.guided_action = guided_action
        self.guided_policy = guided_policy
        self.actions_to_be_bumped = actions_to_be_bumped
        self.all_actions_id = actions_id
        self.action_counter = np.zeros((self._A))
        self.exploration_mode = exploration_mode
        # self.exploration_mode = 'ucb' # For UCB, 'ucb', and for uniform, 'uniform'
        self.c = 0.0005
        # self.log_dir =  str(pathlib.Path(__file__).parent.resolve() / 'models')
        
        # logistics variables
        self.load_model_flag = load_model_flag
        self.failed_operator_name = failed_operator_name

        self.log_dir = log_dir
        self.trial_num = trial_number

        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

        if self.load_model_flag:
            self.load_model(self.failed_operator_name, episode_num=episode_num)

    def init_model(self,random_seed):
        # create model
        #with cp.cuda.Device(0):
        self._model = {}
        np.random.seed(random_seed)
       
        # weights from input to hidden layer   
        self._model['W1'] = np.random.randn(self._D,self._H) / np.sqrt(self._D) # "Xavier" initialization
       
        # weights from hidden to output (action) layer
        self._model['W2'] = np.random.randn(self._H,self._A) / np.sqrt(self._H)
            
        # print("model is: ", self._model)
        # time.sleep(5)		
        self._grad_buffer = { k : np.zeros_like(v) for k,v in self._model.items() } # update buffers that add up gradients over a batch
        self._rmsprop_cache = { k : np.zeros_like(v) for k,v in self._model.items() } # rmsprop memory

    
    # softmax function
    def softmax(self,x):
        probs = np.exp(x - np.max(x, axis=1, keepdims=True))
        probs /= np.sum(probs, axis=1, keepdims=True)
        return probs
        
      
    def discount_rewards(self,r):
        """ take 1D float array of rewards and compute discounted reward """
        discounted_r = np.zeros_like(r)
        running_add = 0
        for t in reversed(range(0, r.size)):
            running_add = running_add * self._gamma + r[t]
            discounted_r[t] = float(running_add)
    
        return discounted_r
    
    def reset_action_counter(self):
        self.action_counter = np.zeros((self._A))

    # feed input to network and get result
    def policy_forward(self,x):
        if(len(x.shape)==1):
            x = x[np.newaxis,...]

        h = x.dot(self._model['W1'])
        
        if np.isnan(np.sum(self._model['W1'])):
            print("W1 sum is nan")
            time.sleep(5)
        if np.isnan(np.sum(self._model['W2'])):
            print("W2 sum is nan")
        
        if np.isnan(np.sum(h)):
            print("nan")
            
            h[np.isnan(h)] = np.random.random_sample()
            h[np.isinf(h)] = np.random.random_sample()
            

        if np.isnan(np.sum(h)):
            print("Still nan!")
        
        
        h[h<0] = 0 # ReLU nonlinearity
        logp = h.dot(self._model['W2'])

        p = self.softmax(logp)
  
        return p, h # return probability of taking actions, and hidden state
        
    
    def policy_backward(self,eph, epdlogp):
        """ backward pass. (eph is array of intermediate hidden states) """
        dW2 = eph.T.dot(epdlogp)  
        dh = epdlogp.dot(self._model['W2'].T)
        dh[eph <= 0] = 0 # backpro prelu
                            
        if(be == "gpu"):
          self._dh_gpu = cuda.to_gpu(dh, device=0)
          self._epx_gpu = cuda.to_gpu(self._epx.T, device=0)
          self._dW1 = cuda.to_cpu(self._epx_gpu.dot(self._dh_gpu) )
        else:
          self._dW1 = self._epx.T.dot(dh) 
    
        return {'W1':self._dW1, 'W2':dW2}
    
    def set_explore_epsilon(self,e):
        self._explore_eps = e
    
    # input: current state/observation
    # output: action index
    def process_step(self, x, exploring, timestep = None, action = None):

        
        # feed input through network and get output action distribution and hidden layer
        aprob, h = self.policy_forward(x)
        # print ("observation inside process step = ",x)


        # if exploring
        if exploring == True and action is None:
            # greedy-e exploration
            rand_e = np.random.uniform()
            #print(rand_e)
            if rand_e < self._explore_eps:
                # set all actions to be equal probability
                        if self.guided_action == True and self.exploration_mode == 'uniform':
                            actions_to_bump_up_sum = sum(aprob[0][i] for i in list(self.actions_to_be_bumped.values()))
                            for i in range(len(aprob[0])): # bump up the probabilities
                                if i in list(self.actions_to_be_bumped.values()):
                                    aprob[0][i] = ((1+actions_to_bump_up_sum)*(aprob[0][i]))/(2*actions_to_bump_up_sum) 
                                else:
                                    aprob[0][i] = aprob[0][i]/2
                        elif self.guided_action == True and self.exploration_mode == 'ucb' and timestep > 0:
                            for i in range(len(aprob[0])):
                                if i in list(self.actions_to_be_bumped.values()):
                                    aprob[0][i] += self.c * math.sqrt(math.log(timestep) / (self.action_counter[i]+0.01))
                                else:
                                    aprob[0][i] -= self.c * math.sqrt(math.log(timestep) / (self.action_counter[i]+0.01))
                                    if aprob[0][i] < 0:
                                        aprob[0][i] = 0
                            sigma_action = np.sum(aprob[0])
                            aprob[0] = [aprob[0][i]/sigma_action for i in range(len(aprob[0]))]
                        else:
                            aprob[0] = [ 1.0/len(aprob[0]) for i in range(len(aprob[0]))]
        elif action is not None:
            
            aprob[0] = [0.01 for i in range(len(aprob[0]))]
            aprob[0][action] = 0.98
        
        
        if np.isnan(np.sum(aprob)):
            # print("Nan found at timestep: ", timestep)
            # time.sleep(3)
            # print(aprob)
            aprob[0] = [ 1.0/len(aprob[0]) for i in range(len(aprob[0]))]
            #input()
        
        aprob_cum = np.cumsum(aprob)
        u = np.random.uniform()
        a = np.where(u <= aprob_cum)[0][0]	

        # record various intermediates (needed later for backprop)
        t = time.time()
        self._xs.append(x) # observation
        self._hs.append(h)
        # print ("self._xs = ", self._xs)

        #softmax loss gradient
        dlogsoftmax = aprob.copy()
        dlogsoftmax[0,a] -= 1 #-discounted reward 
        self._dlogps.append(dlogsoftmax)
        
        t  = time.time()
        # update the action counter
        self.action_counter[a]+=1
        return a
        
    # after process_step, this function needs to be called to set the reward
    def give_reward(self,reward):
        
        # store the reward in the list of rewards
        self._drs.append(reward)
        
    # reset to be used when evaluating
    def reset(self):
        self._xs,self._hs,self._dlogps,self._drs = [],[],[],[] # reset 
        self._grad_buffer = { k : np.zeros_like(v) for k,v in self._model.items() } # update buffers that add up gradients over a batch
        self._rmsprop_cache = { k : np.zeros_like(v) for k,v in self._model.items() } # rmsprop memory


    def throw_out_episode(self):
        self._xs,self._hs,self._dlogps,self._drs = [],[],[],[] # reset array memory

    # this function should be called when an episode (i.e., a game) has finished
    def finish_episode(self):
        # stack together all inputs, hidden states, action gradients, and rewards for this episode
        
        self._epx = np.vstack(self._xs)
        eph = np.vstack(self._hs)
        epdlogp = np.vstack(self._dlogps)
        epr = np.vstack(self._drs)

        
        self._xs,self._hs,self._dlogps,self._drs = [],[],[],[] # reset array memory

        # compute the discounted reward backwards through time
        discounted_epr = (self.discount_rewards(epr))

        epdlogp *= discounted_epr # modulate the gradient with advantage (PG magic happens right here.)
        
        # start_time = time.time()
        grad = self.policy_backward(eph, epdlogp)
        #print("--- %s seconds for policy backward ---" % (time.time() - start_time))
        
        for k in self._model: self._grad_buffer[k] += grad[k] # accumulate grad over batch

    # called to update model parameters, generally every N episodes/games for some N
    def update_parameters(self):
        for k,v in self._model.items():
            g = self._grad_buffer[k] # gradient
            self._rmsprop_cache[k] = self._decay_rate * self._rmsprop_cache[k] + (1 - self._decay_rate) * g**2
            self._model[k] -= self._learning_rate * g / (np.sqrt(self._rmsprop_cache[k]) + 1e-5)
            self._grad_buffer[k] = np.zeros_like(v) # reset batch gradient buffer

    def save_model(self, operator_name, episode_num, path_to_save= None):

        if not path_to_save:
            path_to_save = self.log_dir + os.sep + operator_name + os.sep + "trial_" + str(self.trial_num) + os.sep + operator_name + "_"+ str(episode_num) + '.npz'
        else:
            path_to_save = path_to_save + os.sep + operator_name + "_"+ str(episode_num) + '.npz'
        print ("path_to_save = ", path_to_save)

        np.savez(path_to_save, layer1 = self._model['W1'], layer2 = self._model['W2'])
        print("saved to: ", path_to_save)

    def load_model(self, operator_name, episode_num):
        # if not path_to_load:
        path_to_load = self.log_dir + os.sep + operator_name + os.sep + "trial_" + str(self.trial_num) + os.sep + operator_name + "_"+ str(episode_num) + '.npz'
        data = np.load(path_to_load)
        print ("Loaded model from", path_to_load)
        self._model['W1'] = data['layer1']
        self._model['W2'] = data['layer2']
        return True