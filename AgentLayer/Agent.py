from abc import ABC, abstractmethod


class Agent(ABC):
    """Defines the base structure of Agents

    Attributes
    ----------
        -

    Methods
    -------
        train_model()
            abstract method
        predict()
            abstract method
        save_model()
            abstract method
        load_model()
            abstract method
    """

    @abstractmethod
    def train_model(self, *args, **kwargs):
        pass

    @abstractmethod
    def predict(self, *args, **kwargs):
        pass

    @abstractmethod
    def save_model(self, *args, **kwargs):
        pass

    @abstractmethod
    def load_model(self, *args, **kwargs):
        pass
