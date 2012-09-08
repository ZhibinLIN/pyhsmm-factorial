from __future__ import division
import numpy as np
import operator

import pyhsmm

from internals.states import FactorialStates,\
        FactorialComponentHSMMStates,\
        FactorialComponentHSMMStatesPossibleChangepoints

###################################
#  overall problem wrapper class  #
###################################

class Factorial(pyhsmm.basic.abstractions.ModelGibbsSampling):
    def __init__(self,component_models):
        self.component_models = component_models # should be a list of factorial_component models

        self.states_list = [] # a list of factorial_allstates

    def add_data(self,data,**kwargs):
        # pass in state dimensions so that museqs and varseqs can be maintained
        # kwargs is for changepoints
        self.states_list.append(
                FactorialStates(
                    data=data,
                    component_models=self.component_models,
                    **kwargs))

    def resample_model(self,max_extra_noise,min_extra_noise,niter=25):
        # min_extra_noise useful for numerical stability
        # set up a temperature schedule
        temps = np.zeros(niter)
        cutofftime = int(3./4 * len(temps))
        temps[:cutofftime] = max_extra_noise/2 * (1+np.cos(np.linspace(0,np.pi,cutofftime)))
        temps = np.where(temps < min_extra_noise, min_extra_noise, temps)

        for itr, temp in enumerate(temps):
            # tell each states object to resample each of its component state chains
            # (marginalizing out the component emissions)
            # this call will also delete any instantiated component emissions (in
            # principle)
            for s in self.states_list:
                s.resample(temp_noise=temp)

            # then resample component emissions so that the other models can be
            # resampled
            for s in self.states_list:
                s.instantiate_component_emissions(temp)

            # resample component models (this call will not cause any states objects
            # referenced by self.states_list to resample, but the parameter
            # resampling involved in resampling these models will need the component
            # emissions)
            for c in self.component_models:
                c.resample_model()

    def generate(self,T,keep=True):
        tempstates = \
                FactorialStates(
                    data=None,
                    T=T,
                    keep=keep,
                    component_models=self.component_models,
                )
        sumobs, allobs, allstates = tempstates.sumobs, tempstates.allobs, tempstates.allstates

        if keep:
            tempstates.added_with_generate = True
            tempstates.data = sumobs
            self.states_list.append(tempstates)

        return sumobs, allobs, allstates

    def plot(self,color=None): # TODO
        # this is ALWAYS useful
        raise NotImplementedError


######################################
#  classes for the component models  #
######################################

# NOTE: component_models must have scalar gaussian observation
# distributions! this code, which references the same cached means and vars as
# the states, requires it!
class FactorialComponentHSMM(pyhsmm.models.HSMM):
    def __init__(self,**kwargs): # no explicit parameter naming because DRY
        assert 'obs_distns' in kwargs
        obs_distns = kwargs['obs_distns']
        self.means, self.vars = np.zeros(len(obs_distns)), np.zeros(len(obs_distns))
        for idx, distn in enumerate(obs_distns):
            assert isinstance(distn,pyhsmm.basic.distributions.ScalarGaussian),\
                    'Factorial model components must have scalar Gaussian observation distributions!'
            distn.mubin = self.means[idx,...]
            distn.sigmasqbin = self.vars[idx,...]
            self.means[idx] = distn.mu
            self.vars[idx] = distn.sigmasq
        super(FactorialComponentHSMM,self).__init__(**kwargs)

    def generate(self,T,keep=True):
        # just like parent method, except uses our own states class
        tempstates = \
                FactorialComponentHSMMStates(
                        means=self.means,
                        vars=self.vars,
                        T=T,
                        state_dim=self.state_dim,
                        obs_distns=self.obs_distns,
                        dur_distns=self.dur_distns,
                        transition_distn=self.trans_distn,
                        initial_distn=self.init_state_distn,
                        trunc=self.trunc
                )
        return self._generate(tempstates,keep)

    def add_factorial_sumdata(self,data):
        assert data.ndim == 1 or data.ndim == 2
        data = np.reshape(data,(-1,1))
        self.states_list.append(
                FactorialComponentHSMMStates(
                    data=data,
                    means=self.means,
                    vars=self.vars,
                    T=data.shape[0],
                    state_dim=len(self.obs_distns),
                    obs_distns=self.obs_distns,
                    dur_distns=self.dur_distns,
                    transition_distn=self.trans_distn,
                    initial_distn=self.init_state_distn,
                    trunc=self.trunc,
                    ))
        # the added states object will get its resample() method called, but
        # since that object doesn't do anything at the moment,
        # resample_factorial needs to be called higher up

class FactorialComponentHSMMPossibleChangepoints(FactorialComponentHSMM):
    def add_factorial_sumdata(self,data,changepoints):
        if data is not None:
            assert data.ndim == 1 or data.ndim == 2
            data = np.reshape(data,(-1,1))
        self.states_list.append(
                FactorialComponentHSMMStatesPossibleChangepoints(
                    data=data,
                    changepoints=changepoints,
                    means=self.means,
                    vars=self.vars,
                    T=data.shape[0],
                    state_dim=len(self.obs_distns),
                    obs_distns=self.obs_distns,
                    dur_distns=self.dur_distns,
                    transition_distn=self.trans_distn,
                    initial_distn=self.init_state_distn,
                    trunc=self.trunc,
                    ))

    def generate(self,T,keep=True):
        # just like parent method, except uses our own states class
        tempstates = \
                FactorialComponentHSMMStatesPossibleChangepoints(
                        means=self.means,
                        vars=self.vars,
                        T=T,
                        state_dim=self.state_dim,
                        obs_distns=self.obs_distns,
                        dur_distns=self.dur_distns,
                        transition_distn=self.trans_distn,
                        initial_distn=self.init_state_distn,
                        trunc=self.trunc
                )
        return self._generate(tempstates,keep)


# TODO hmm versions below here

# class factorial_component_hmm(pyhsmm.models.hmm):
#     means = None
#     vars = None
#     def add_factorial_sumdata(self,data,**kwargs):
#         self.states_list.append(pyhsmm.plugins.factorial.states.factorial_component_hmm_states(data,**kwargs))

# class factorial_component_hmm_possiblechangepoints(pyhsmm.models.hmm):
#     means = None
#     vars = None
#     def add_factorial_sumdata(self,data,changepoints,**kwargs):
#         self.states_list.append(pyhsmm.plugins.factorial.states.factorial_component_hmm_states_possiblechangepoints(data,changepoints,**kwargs))

# TODO make transitions distribution hierarchical
class HierarchicalHSMM(object):
    # maintains one transition distribution and one initial state distribution
    # but hierarchies of observation and duration distributions
    def __init__(self,HSMMclass,alpha,gamma,obs_distn_classes,dur_distn_classes):
        self.HSMMclass = HSMMclass
        self.obs_distn_classes = obs_distn_classes
        self.dur_distn_classes = dur_distn_classes

        self._instances = []

        self.init_state_distn = self._InitState(self,
                state_dim=len(obs_distn_classes),rho=3)
        self.trans_distn = self._Transitions(self,
                alpha=alpha,gamma=gamma,state_dim=len(obs_distn_classes))

        # TODO this coding is a bit is weird
        self.init_state_distn.resample, self.init_state_distn._resample = \
                self.init_state_distn._resample, self.init_state_distn.resample
        self.trans_distn.resample, self.trans_distn._resample = \
                self.trans_distn._resample, self.trans_distn.resample

    def new_instance(self):
        self._instances.append(self.HSMMclass(alpha=None,gamma=None,
            transitions=self.trans_distn,initial_state_distn=self.init_state_distn,
            obs_distns=[o.new_instance() for o in self.obs_distn_classes],
            dur_distns=[d.new_instance() for d in self.dur_distn_classes]
            ))
        return self._instances[-1]

    def resample_model(self):
        for model in self._instances:
            model.resample_model()

        for oc in self.obs_distn_classes:
            oc.resample()

        for dc in self.dur_distn_classes:
            dc.resample()

    def _resample_transitions(self):
        # aggregate states across all models and all stateseqs
        self.trans_distn._resample(reduce(operator.add,
            [[s.stateseq for s in m.states_list] for m in self._instances]))

    def _resample_initstate(self):
        # aggregate states across all models and all stateseqs
        self.init_state_distn._resample(reduce(operator.add,
            [[s.stateseq[0] for s in m.states_list] for m in self._instances]))

    class _Transitions(pyhsmm.internals.transitions.HDPHSMMTransitions):
        # override resample to call HierarchicalHSMM so that it can use everyone's
        # statistics
        def __init__(self,classref,*args,**kwargs):
            self.classref = classref
            super(HierarchicalHSMM._Transitions,self).__init__(*args,**kwargs)

        def _resample(self,*args,**kwargs):
            self.classref._resample_transitions()

        def resample(self,*args,**kwargs):
            super(HierarchicalHSMM._Transitions,self).resample(*args,**kwargs)

    class _InitState(pyhsmm.internals.initial_state.InitialState):
        # override resample to call HierarchicalHSMM so that it can use everyone's
        # statistics
        def __init__(self,classref,*args,**kwargs):
            self.classref = classref
            super(HierarchicalHSMM._InitState,self).__init__(*args,**kwargs)

        def _resample(self,*args,**kwargs):
            self.classref._resample_initstate()

        def resample(self,*args,**kwargs):
            super(HierarchicalHSMM._InitState,self).resample(*args,**kwargs)


# TODO making transitions 'simlar but not same' is better! plus it'd make the
# code more symmetrical, with trans/initstate hierarchical objects just like
# those for obs and dur distns. and HierarchicalHSMM would be super trivial!

