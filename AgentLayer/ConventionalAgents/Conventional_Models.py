from abc import ABC, abstractmethod
from AgentLayer.Agent import Agent


class ConventionalModel(Agent, ABC):

    @abstractmethod
    def train_model():
        pass

    @abstractmethod
    def predict():
        pass

    @abstractmethod
    def save_model():
        pass

    @abstractmethod
    def load_model():
        pass

    @abstractmethod
    def _return_predict():
        pass

    @abstractmethod
    def _weight_optimization():
        pass

