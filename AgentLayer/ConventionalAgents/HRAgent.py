from AgentLayer.ConventionalAgents.ConventionalAgent import ConventionalAgent
import numpy as np
from sklearn.linear_model import HuberRegressor
import pandas as pd
import pickle
from pypfopt import EfficientFrontier
from pypfopt import risk_models
from pypfopt import objective_functions
from utils import read_config_file


config = read_config_file()


class HRAgent(ConventionalAgent):
    """Provides methods Huber Regressor Agent.

    Attributes
    ----------
        model : sklearn.model object
            conventional agent model

    Methods
    -------
        train_model()
            trains the model.
        get_params()
            Get parameters for this estimator.
        predict()
            main prediction method. 
            does prediction using _return_predict() and _weight_optimizion()
            helper functions.
        save_model()
            saves the model.
        load_model()
            loads the model.
        _return_predict()
            predicts the expected return.
            helper function for the main predict method.
        _weight_optimization()
            optimizes weights using efficient frontier.
            helper function for the main predict method.
    """

    def __init__(self, *,
                 epsilon=1.35,
                 max_iter=1000,
                 alpha=0.0001,
                 warm_start=False,
                 fit_intercept=True,
                 tol=1e-05):
        """Initialize Huber Regressor Agent object

        Args:
            epsilon (float, optional): The parameter epsilon controls the number of samples that should be classified as outliers.. Defaults to 1.35.
            max_iter (int, optional): Maximum number of iterations . Defaults to 1000.
            alpha (float, optional): Regularization parameter.. Defaults to 0.0001.
            warm_start (bool, optional): This is useful if the stored attributes of a previously used model has to be reused. 
            If set to False, then the coefficients will be rewritten for every call to fit. Defaults to False.
            fit_intercept (bool, optional): Whether or not to fit the intercept. Defaults to True.
            tol (float, optional): The iteration will stop when max{|proj g_i | i = 1, ..., n} <= tol where pg_i is the i-th component of the projected gradient. Defaults to 1e-05.
        """

        self.model = HuberRegressor(epsilon=epsilon,
                                    max_iter=max_iter,
                                    alpha=alpha,
                                    warm_start=warm_start,
                                    fit_intercept=fit_intercept,
                                    tol=tol)

    def get_params(self, deep=True):
        """Get parameters for this estimator.

        Args:
            deep (bool, optional): If True, will return the parameters for this estimator and contained subobjects that are estimators. Defaults to True.

        Returns:
            dict: parameters
        """
        return self.model.get_params(deep=deep)

    def train_model(self, train_x, train_y, **train_params):
        """Trains the model and saves it to class.

        Args:
            train_x (pd.DataFrame): train_x data
            train_y (pd.DataFrame): train_y data
            train_params (dict) : training parameters
        """
        try:
            trained = self.model.fit(train_x, train_y.ravel(), **train_params)
            self.model = trained
            print("Model trained succesfully")
        except Exception as e:
            print("training unsuccessful")

    def predict(self,
                test_data,
                initial_capital=1000000,
                transaction_cost_pct=0.001,
                feature_list=config["TEST_PARAMS"]["HR_PARAMS"]["feature_list"]
                ):
        """Main prediction method.

        Args:
            test_data (pd.DataFrame): test data
            initial_capital (int) : initial capital
            feature_list (list) : a list of features to be used for prediction
            transaction_cost_pct (float) : transaction cost

        Returns:
            pd.DataFrame: portfolio with dates and account value
            pd.DataFrame: dataframe that holds info for each ticker for each day the weight
            and predicted y value.
        """

        meta_coefficient = {"date": []}
        for i in test_data.tic:
            meta_coefficient[i] = []
        unique_trade_date = test_data.date.unique()
        weight_arr = [
            np.array([1/len(test_data.tic.unique())]*len(test_data.tic.unique()))]
        portfolio = pd.DataFrame(index=range(1), columns=unique_trade_date)
        portfolio.loc[0, unique_trade_date[0]] = initial_capital
        for i in range(len(unique_trade_date) - 1):
            mu, sigma, tics, df_current, df_next = self._return_predict(
                unique_trade_date, test_data, i, tech_indicator_list)

            portfolio_value, weight_arr = self._weight_optimization(
                i, unique_trade_date, meta_coefficient, mu, sigma, tics, portfolio, df_current, df_next, transaction_cost_pct, weight_arr)

        portfolio = portfolio_value
        portfolio = portfolio.T
        portfolio.columns = ['account_value']
        portfolio = portfolio.reset_index()
        portfolio.columns = ['date', 'account_value']

        meta_coefficient = pd.DataFrame(meta_coefficient).set_index("date")
        return portfolio, meta_coefficient

    def _return_predict(self, unique_trade_date, test_data, i, feature_list):
        """Predicts the expected return using  technical indicators.
            Helper function for the main predict method.

        Args:
            unique_trade_date (datetime): unique dates in the test data
            test_data (pd.DataFrame): test data
            i (int): index for the loop
            feature_list (list) : a list of features to be used for prediction

        Returns:
            pd.DataFrame: current date
            pd.DataFrame: next date
            list: tickers
            np.ndarray: predicted y_values (expected returns)
            np.ndarray: risk (covarience matrix)
        """

        current_date = unique_trade_date[i]
        next_date = unique_trade_date[i + 1]

        df_current = test_data[test_data.date ==
                               current_date].reset_index(drop=True)
        df_next = test_data[test_data.date ==
                            next_date].reset_index(drop=True)

        tics = df_current['tic'].values
        features = df_current[feature_list].values

        predicted_y = self.model.predict(features)
        mu = predicted_y
        sigma = risk_models.sample_cov(
            df_current.return_list[0], returns_data=True)

        return mu, sigma, tics, df_current, df_next

    def _weight_optimization(self, i, unique_trade_date, meta_coefficient, mu, sigma, tics, portfolio, df_current, df_next, transaction_cost_pct, weight_arr):
        """Optimizes weights using efficient frontier.
            Helper function for the main predict method.

        Args:
            i (int): index for the loop
            unique_trade_date (datetime): unique dates in the test data
            meta_coefficient (pd.DataFrame): empty DataFrame to be filled with weights and tickers.
            mu (pd.Series): predicted y values (expected returns)
            sigma (np.ndarray): covarience matrix
            tics (list): tickers
            portfolio (pd.DataFrame): DataFrame to hold portfolio info
            df_current (pd.DataFrame): current date
            df_next (pd.DataFrame): next date
            transaction_cost_pct (float) : transaction cost
            weight_arr (np.array) : initial weights

        Returns:
            pd.DataFrame: portfolio 
        """
        current_date = unique_trade_date[i]
        predicted_y_df = pd.DataFrame(
            {"tic": tics.reshape(-1,), "predicted_y": mu.reshape(-1,)})
        min_weight, max_weight = 0, 1

        ef = EfficientFrontier(mu, sigma)
        w_prev = np.array(weight_arr[-1], dtype=object)
        ef.add_objective(objective_functions.transaction_cost,
                         w_prev=w_prev, k=transaction_cost_pct)
        weights = ef.nonconvex_objective(
            objective_functions.sharpe_ratio,
            objective_args=(ef.expected_returns, ef.cov_matrix),
            weights_sum_to_one=True,
            constraints=[
                # greater than min_weight
                {"type": "ineq", "fun": lambda w: w - min_weight},
                # less than max_weight
                {"type": "ineq", "fun": lambda w: max_weight - w},
            ],
        )

        weight_df = {"tic": [], "weight": []}
        meta_coefficient["date"] += [current_date]

        for item in weights:
            weight_df['tic'] += [item]
            weight_df['weight'] += [weights[item]]

        weight_df = pd.DataFrame(weight_df).merge(predicted_y_df, on=['tic'])

        tics_list = list(weight_df['tic'])
        weights_list = list(weight_df['weight'])
        new_weights = []
        for j in range(len(tics_list)):
            meta_coefficient[tics_list[j]] += [weights_list[j]]
            new_weights.append(weights_list[j])
        weight_arr.append(new_weights)
        cap = portfolio.iloc[0, i]
        # current cash invested for each stock
        current_cash = [element * cap for element in list(weights.values())]
        # current held shares
        current_shares = list(np.array(current_cash) /
                              np.array(df_current.close))
        # next time period price
        next_price = np.array(df_next.close)
        portfolio.iloc[0, i+1] = np.dot(current_shares, next_price)

        return portfolio, weight_arr

    def save_model(self, file_name):
        """Saves the model

        Args:
            file_name (str): file name for saving the model
        """
        with open(file_name, 'wb') as files:
            pickle.dump(self.model, files)
        print("Model saved succesfully.")

    def load_model(self, file_name):
        """Loads the model

        Args:
            file_name (str): file to be loaded.

        Returns:
            sklearn.model: loaded model
        """
        with open(file_name, 'rb') as f:
            self.model = pickle.load(f)
        print("Model loaded succesfully.")
        return self.model
