# -*- coding: utf-8 -*-
"""ml_chess_predict.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1kJdwveWcT7SrmYQlp-NmlVqGGDlxW6Da

# Chess Winner Prediction Using ML Models

The goal is to predict chess matches winner using the available data from lichess dataset. And also, explore what is the impact of rankings and openings (strategy and turns taken) in winning the game. You can inspect and download the dataset from [this url](https://www.kaggle.com/datasets/datasnaek/chess).

## About Dataset

Extracted from official dataset index.

**General Info**

This is a set of just over 20,000 games collected from a selection of users on the site Lichess.org, and how to collect more. This set contains the following features:


- Game ID;
- Rated (T/F);
- Start Time;
- End Time;
- Number of Turns;
- Game Status;
- Winner;
- Time Increment;
- White Player ID;
- White Player Rating;
- Black Player ID;
- Black Player Rating;
- All Moves in Standard Chess Notation;
- Opening Eco (Standardised Code for any given opening, [list here](https://www.365chess.com/eco.php));
- Opening Name;
- Opening Ply (Number of moves in the opening phase)

Data was collected using the [Lichess API](https://github.com/ornicar/lila), which enables collection of any given users game history.

**Possible Uses**

Lots of information is contained within a single chess game, let alone a full dataset of multiple games. It is primarily a game of patterns, and data science is all about detecting patterns in data, which is why chess has been one of the most invested in areas of AI in the past. This dataset collects all of the information available from 20,000 games and presents it in a format that is easy to process for analysis of, for example, what allows a player to win as black or white, how much meta (out-of-game) factors affect a game, the relationship between openings and victory for black and white and more.

## Imports
"""

# Commented out IPython magic to ensure Python compatibility.
from sklearn.impute import KNNImputer
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.neighbors import KNeighborsClassifier
from sklearn.model_selection import GridSearchCV
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.preprocessing import OneHotEncoder
from sklearn.metrics import accuracy_score
from sklearn import preprocessing
from sklearn import metrics
from sklearn.metrics import confusion_matrix
from sklearn.tree import DecisionTreeClassifier
from sklearn.pipeline import Pipeline
import seaborn as sn
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
# only on notebooks
# %matplotlib inline

"""## Exploratory Data Analysis"""

chess = pd.read_csv('games.csv')

chess.info()

chess.columns

chess.describe()

print(chess['winner'].unique())

print(chess['victory_status'].unique())

"""### Analysing correlations"""

# https://www.statology.org/one-hot-encoding-in-python/

def cat_encoder(df, var_array):
    encoded, categories = var_array.factorize()
    print('first values: ')
    print(encoded[:10])
    print(categories)
    encoder = OneHotEncoder()
    one_hot = encoder.fit_transform(encoded.reshape(-1, 1))
    one_hot_df = pd.DataFrame(one_hot.toarray())
    return df.join(one_hot_df)

chess = cat_encoder(chess, chess['winner'])

chess.rename({0: 'white_wins', 1: 'black_wins', 2: 'draw'}, axis=1, inplace=True)

"""Dropping draw column and values to fit problem into binnary classification"""

draws = chess.loc[chess['winner'] == 'draw']
chess.drop(draws.index, inplace=True)

chess.drop(['draw'], axis=1, inplace=True)

train_set, test_set = train_test_split(chess, test_size=0.2, random_state=42)
exp_chess = train_set.copy()
corr_matrix = exp_chess.corr()

corr_matrix['white_wins'].sort_values(ascending=False)

corr_matrix['black_wins'].sort_values(ascending=False)

"""#### Exploratory assumptions

* There are no apparent linear relations between features.
* It's easier to win on white side.
* Surprisingly, player's ranks does not influence victory probabilities.
* The most common method to win is ```resign```.
* Black have better chances on longer games, winning by ```outoftime```.
* Simetrically, white have better chances on short ```opening_ply```.
* The longer the game, more chances black have to win.

## Preprocessing Pipeline
"""

class ColumnDropper(BaseEstimator, TransformerMixin):
    def __init__(self, corr=False):
        self.columns = ["id", "created_at", "last_move_at", "increment_code", "white_id", "white_rating", "black_id",
                        "black_rating", "moves", "opening_eco", "opening_name", "opening_ply"]
        if corr:
            self.columns.append('white_wins')
            self.columns.append('black_wins')

    def fit(self, X, y=None):
        return self

    def transform(self, X, y=None):
        return X.drop(self.columns, axis=1)

class CatEncoder(BaseEstimator, TransformerMixin):
    def __init__(self):
        self.cats = ['winner', 'rated', 'victory_status']

    def fit(self, X, y=None):
        return self
    
    def transform(self, X, y=None):
        le = LabelEncoder()
        db = X.copy()
        for cat in self.cats:
            db[cat] = le.fit_transform(db[cat])
        return db

class MissValImputer(BaseEstimator, TransformerMixin):
    def __init__(self):
        pass
    
    def fit(self, X, y=None):
        return self
    
    def transform(self, X, y=None):
        db = X.copy()
        imputer = KNNImputer(missing_values=np.nan, n_neighbors=5)
        imputer.fit(db)
        db[:] = imputer.transform(db)
        return db

def normalize(val):
    val = (val-np.min(val))/(np.max(val)-np.min(val))
    return val

class Normalizer(BaseEstimator, TransformerMixin):
    def __init__(self, columns=None):
        if columns:
            self.columns = columns
        else:
            self.columns = ['turns']
    
    def fit(self, X, y=None):
        return self
    
    def transform(self, X, y=None):
        db = X.copy()
        for col in self.columns:
            db[col] = normalize(db[col])
        return db

preprocess_pipeline = Pipeline([
    ('col_dropper', ColumnDropper(corr=True)),
    ('cat_encoder', CatEncoder()),
    ('miss_imputer', MissValImputer()),
    ('normalizer', Normalizer())
])

"""#### Final dataset status"""

chess = preprocess_pipeline.fit_transform(chess)
chess.head()

"""## Splitting Dataset using Holdout Method """

chess_data = chess.loc[:, chess.columns != 'winner']
chess_labels = chess['winner']

X_train, X_test, y_train, y_test = train_test_split(chess_data, chess_labels, test_size=0.30, random_state=42)

"""## Training and fine tuning Models

We will evaluate performance on the following models:

- K-nearest Neighbors
- Decision Tree
- Naive Bayes
- Neural Networks
"""

def grid_scores(model):
    model.fit(X_train, y_train)
    print(f"best mean cross-validation score: {model.best_score_}")
    print(f"best parameters: {model.best_params_}")
    # do the final evaluation
    print(f"test-set score: {model.score(X_test, y_test):.3f}")

def train_eval_model(model):
    model.fit(X_train, y_train)
    train_pred = model.predict(X_train)
    test_pred = model.predict(X_test)
    train_acc = accuracy_score(y_train, train_pred)
    test_acc = accuracy_score(y_test, test_pred)
    return (train_acc, test_acc)

"""### K-nearest Neighbors"""

knn_params = {'n_neighbors': np.arange(1, 15, 2)}

knn_grid = GridSearchCV(KNeighborsClassifier(),
                        param_grid=knn_params, cv=10, return_train_score=True)

grid_scores(knn_grid)

"""### Decision Tree Classifier"""

dec_tree = DecisionTreeClassifier()
train_tree_acc, test_tree_acc = train_eval_model(dec_tree)
print('train accuracy: ', train_tree_acc)
print('test accuracy: ', test_tree_acc)

tree_para = {'criterion': ['gini', 'entropy'], 'max_depth': [
    4, 5, 6, 7, 8, 9, 10, 11, 12, 15, 20, 30, 40, 50, 70, 90, 120, 150]}

tree_grid = GridSearchCV(DecisionTreeClassifier(), tree_para, cv=10, return_train_score=True)

grid_scores(tree_grid)

"""### Naive Bayes Classifier"""

from sklearn.naive_bayes import GaussianNB

gauss_nb_model = GaussianNB()

train_nb_acc, test_nb_acc = train_eval_model(gauss_nb_model)
print('train acc: ', train_nb_acc)
print('test acc: ', test_nb_acc)

gauss_nb_param = {
    'var_smoothing': np.logspace(0, -9, num=100)
}

gauss_nb_grid = GridSearchCV(GaussianNB(), gauss_nb_param, cv=10, n_jobs=-1)

grid_scores(gauss_nb_grid)

"""### Neural Network

If we get more time: https://pytorch.org/tutorials/beginner/basics/optimization_tutorial.html
"""

from sklearn.neural_network import MLPClassifier

nn_model = MLPClassifier(solver='lbfgs', alpha=1e-5, hidden_layer_sizes=(5, 2), random_state=42)
train_nn_acc, test_nn_acc = train_eval_model(nn_model)
print('train acc: ', train_nn_acc)
print('test acc: ', test_nn_acc)

from sklearn.preprocessing import StandardScaler

scaler = StandardScaler()

GRID = [
    {'scaler': [StandardScaler()],
     'estimator': [MLPClassifier(random_state=42)],
     'estimator__solver': ['adam'],
     'estimator__learning_rate_init': [0.0001],
     'estimator__max_iter': [300],
     'estimator__hidden_layer_sizes': [(500, 400, 300, 200, 100), (400, 400, 400, 400, 400), (300, 300, 300, 300, 300), (200, 200, 200, 200, 200)],
     'estimator__activation': ['logistic', 'tanh', 'relu'],
     'estimator__alpha': [0.0001, 0.001, 0.005],
     'estimator__early_stopping': [True, False]
     }
]

PIPELINE = Pipeline([('scaler', StandardScaler()), ('estimator', MLPClassifier())])

# grid_search = GridSearchCV(estimator=PIPELINE, param_grid=GRID,
#                            # average='macro'),
#                            n_jobs=-1, cv=5, refit=True, verbose=1,
#                            return_train_score=False)

# grid_search.fit(X_train, y_train)