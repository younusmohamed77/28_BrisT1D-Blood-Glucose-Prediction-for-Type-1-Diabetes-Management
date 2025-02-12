unbase/baseline.py(89.62 kB)
"""
@author:yunsuxiaozi
@start_time:2024/09/27
@update_time:2024/11/14
"""
import polars as pl#similar to pandas, but with better performance when dealing with large datasets.
import pandas as pd#read csv,parquet
import numpy as np#for scientific computation of matrices
from scipy.stats import kurtosis#calculate kurt
#powerful plot libraries
import matplotlib.pyplot as plt
import seaborn as sns

#current supported kfold
from sklearn.model_selection import KFold,StratifiedKFold,StratifiedGroupKFold,GroupKFold
#metrics
from sklearn.metrics import roc_auc_score,f1_score,matthews_corrcoef
#models(lgb,xgb,cat,ridge,lr,tabnet)
from sklearn.linear_model import Ridge,LinearRegression,LogisticRegression
from  lightgbm import LGBMRegressor,LGBMClassifier,log_evaluation,early_stopping
from catboost import CatBoostRegressor,CatBoostClassifier
from xgboost import XGBRegressor,XGBClassifier
from pytorch_tabnet.tab_model import TabNetRegressor,TabNetClassifier
import optuna#automatic hyperparameter optimization framework

import ast#parse Python list strings  transform '[a,b,c]' to [a,b,c]
import copy#copy object
import gc#rubbish collection
import dill#serialize and deserialize objects (such as saving and loading tree models)
from colorama import Fore, Style #print colorful text
import os#interact with operation system

#deal with text
import re#python's built-in regular expressions.
from sklearn.feature_extraction.text import CountVectorizer,TfidfVectorizer#word2vec feature
import ftfy#fixes text for you,correct unicode issues.
import nltk #Natural Language toolkit
from nltk.corpus import stopwords#import english stopwords
import emoji#deal with emoji in natrual language

import warnings#avoid some negligible errors
#The filterwarnings () method is used to set warning filters, which can control the output method and level of warning information.
warnings.filterwarnings('ignore')

import random#provide some function to generate random_seed.
#set random seed,to make sure model can be recurrented.
def seed_everything(seed):
    np.random.seed(seed)#numpy's random seed
    random.seed(seed)#python built-in random seed
seed_everything(seed=2024)

class Yunbase():
    def __init__(self,num_folds:int=5,
                      models:list[tuple]=[],
                      FE=None,
                      drop_cols:list[str]=[],
                      seed:int=2024,
                      objective:str='regression',
                      metric:str='mse',
                      nan_margin:float=0.95,
                      group_col=None,
                      num_classes=None,
                      target_col:str='target',
                      infer_size:int=10000,
                      save_oof_preds:bool=True,
                      save_test_preds:bool=True,
                      device:str='cpu',
                      one_hot_max:int=50,
                      custom_metric=None,
                      use_optuna_find_params:int=0,
                      optuna_direction=None,
                      early_stop:int=100,
                      use_pseudo_label:bool=False,
                      use_high_corr_feat:bool=True,
                      cross_cols:list[str]=[],
                      labelencoder_cols:list[str]=[],
                      list_cols:list[str]=[],
                      list_gaps:list[int]=[1],
                      word2vec_models:list[tuple]=[],
                      text_cols:list[str]=[],
                      plot_feature_importance:bool=False,
                      log:int=100,
                      exp_mode:bool=False,
                      use_reduce_memory:bool=False,
                      AGGREGATIONS:list[str]=['nunique','count','min','max','first','last', 'mean','median','sum','std','skew'],#kurtosis
                )->None:
        """
        num_folds             :the number of folds for k-fold cross validation.
        models                :Built in 3 GBDTs as baseline, you can also use custom models,
                               such as models=[(LGBMRegressor(**lgb_params),'lgb')]
        FE                    :In addition to the built-in feature engineer, you can also customize feature engineer.
        drop_cols             :The column to be deleted after all feature engineering is completed.
        seed                  :random seed.
        objective             :what task do you want to do?regression,binary or multi_class?
        metric                :metric to evaluate your model.
        nan_margin            :when the proportion of missing values in a column is greater than, we delete this column.
        group_col             :if you want to use groupkfold,then define this group_col.
        num_classes           :if objectibe is multi_class,you should define this class.
        target_col            :the column that you want to predict.
        infer_size            :the test data might be large,we can predict in batches.
        save_oof_preds        :you can save OOF for offline study.
        save_test_preds       :you can save test_preds.For multi classification tasks, 
                               the predicted result is the category.If you need to save the probability of the test_data,
                               you can save test_preds.
        device                :GBDT can training on GPU,you can set this parameter like NN.
        one_hot_max           :If the nunique of a column is less than a certain value, perform one hot encoder.
        custom_metric         :your custom_metric,when objective is multi_class,y_pred in custom(y_true,y_pred) is probability.            
        use_optuna_find_params:count of use optuna find best params,0 is not use optuna to find params.
                               Currently only LGBM is supported.
        optuna_direction      :'minimize' or 'maximize',when you use custom metric,you need to define 
                               the direction of optimization.
        early_stop            :Common parameters of GBDT.
        use_pseudo_label      :Whether to use pseudo labels.When it is true,adding the test data 
                               to the training data and training again after obtaining the predicted 
                               results of the test data.
        use_high_corr_feat    :whether to use high correlation features or not. 
        labelencoder_cols     :Convert categorical string variables into [1,2,……,n].
        list_cols             :If the data in a column is a list or str(list), this can be used to extract features.
        list_gaps             :extract features for list_cols.example=[1,2,4]
        word2vec_models       :Use models such as tfidf to extract features of string columns 
                               example:word2vec_models=[(TfidfVectorizer(max_features=250,ngram_range=(2,3)),col,model_name)]
        text_cols             :extract features of words, sentences, and paragraphs from text here.
        plot_feature_importance:after model training,whether print feature importance or not
        log                   :log trees are trained in the GBDT model to output a validation set score once.
        exp_mode              :In regression tasks, the distribution of target_col is a long tail distribution, 
                               and this parameter can be used to perform log transform on the target_col.
        use_reduce_memory     :if use function reduce_mem_usage(),then set this parameter True.
        cross_cols            :Construct features for adding, subtracting, multiplying, and dividing these columns.
        """
        
        #currented supported metric
        self.supported_metrics=['custom_metric',#your custom_metric
                                'mae','rmse','mse','medae','rmsle','msle','mape','r2',#regression
                                'auc','logloss','f1_score','mcc',#binary metric
                                'accuracy','multi_logloss',#multi_class or classification
                               ]
        #current supported models
        self.supported_models=['lgb','cat','xgb','ridge','LinearRegression','LogisticRegression','tabnet']
        #current supported kfold.
        self.supported_kfolds=['KFold','GroupKFold','StratifiedKFold','StratifiedGroupKFold','purged_CV']
        #current supported objective.
        self.supported_objectives=['binary','multi_class','regression']
        
        print(f"Currently supported metrics:{self.supported_metrics}")
        print(f"Currently supported models:{self.supported_models}")
        print(f"Currently supported kfolds:{self.supported_kfolds}")
        print(f"Currently supported objectives:{self.supported_objectives}")
        
        self.num_folds=num_folds
        self.seed=seed
        self.models=models
        self.FE=FE
        self.drop_cols=drop_cols
        
        self.objective=objective.lower()
        #binary multi_class,regression
        if self.objective not in self.supported_objectives:
            raise ValueError("Wrong or currently unsupported objective.")
        
        self.custom_metric=custom_metric#function
        if self.custom_metric!=None:
            self.metric='custom_metric'
        else:
            self.metric=metric.lower()
        if self.metric not in self.supported_metrics and self.custom_metric==None:
            raise ValueError("Wrong or currently unsupported metric,You can customize the evaluation metrics using 'custom_metric'.")
        
        self.nan_margin=nan_margin
        if self.nan_margin<0 or self.nan_margin>1:
            raise ValueError("nan_margin must be within the range of 0 to 1.")
        self.group_col=group_col
        self.target_col=target_col
        self.infer_size=infer_size
        if self.infer_size<=0 or type(self.infer_size) is not int:
            raise ValueError("infer size must be greater than 0 and must be int.")  
        self.save_oof_preds=save_oof_preds
        if self.save_oof_preds not in [True,False]:
            raise ValueError("save_oof_preds must be True or False.")  
        self.save_test_preds=save_test_preds
        if self.save_test_preds not in [True,False]:
            raise ValueError("save_test_preds must be True or False.")
        self.num_classes=num_classes
        self.device=device.lower()
        if (self.objective=='binary') and self.num_classes!=2:
            raise ValueError("num_classes must be 2.")
        elif (self.objective=='multi_class') and (self.num_classes==None):
            raise ValueError("num_classes must be a number(int).")
        self.one_hot_max=one_hot_max
        
        self.use_optuna_find_params=use_optuna_find_params
        self.optuna_direction=optuna_direction
        self.direction2metric={
            'maximize':['accuracy','auc','f1_score','mcc',#classification
                        'r2'#regression
                       ],
            'minimize':['medae','mape','mae','rmse','mse','rmsle','msle',#regression
                        'logloss','multi_logloss'#classification
                       ]
        }
        if (self.use_optuna_find_params) and (self.custom_metric!=None) and self.optuna_direction not in ['minimize','maximize']:
            raise ValueError("optuna_direction must be 'minimize' or 'maximize'.")
        self.early_stop=early_stop
        self.test=None#test data will be replaced when call predict function.
        self.use_pseudo_label=use_pseudo_label
        self.use_high_corr_feat=use_high_corr_feat
        self.cross_cols=cross_cols
        self.labelencoder_cols=labelencoder_cols
        self.list_cols=list(set(list_cols))
        self.list_gaps=sorted(list_gaps)
        self.word2vec_models=word2vec_models
        self.word2vec_cols=[]#origin cols that need to use in tfidf model.
        self.text_cols=text_cols#extract features of words, sentences, and paragraphs from text here.
        self.plot_feature_importance=plot_feature_importance
        #Due to the presence of special characters in some column names, 
        #they cannot be directly passed into the LGB model training, so conversion is required
        self.col2name=None
        self.log=log
        self.exp_mode=exp_mode
        if self.exp_mode not in [True,False]:
            raise ValueError("exp_mode must be True or False.")  
        if (self.objective!='regression') and (self.exp_mode==True):
            raise ValueError("exp_mode must be False in classification task.")
        self.use_reduce_memory=use_reduce_memory
        if self.use_reduce_memory not in [True,False]:
            raise ValueError("use_reduce_memory must be True or False.")  
        #when log transform, it is necessary to ensure that the minimum value of the target is greater than 0.
        #so target=target-min_target. b is -min_target.
        self.exp_mode_b=0
        
        #common AGGREGATIONS
        self.AGGREGATIONS = AGGREGATIONS
        self.sample_weight=1
        
        #If inference one batch of data at a time requires repeatedly loading the model,
        #it will increase the program's running time.we need to save  in dictionary when load.
        self.trained_models=[]#trained model
        self.trained_le={}
        self.trained_wordvec={}
        self.onehot_valuecounts={}
        #make folder to save model trained.such as GBDT,word2vec.
        self.model_save_path="Yunbase_info/"
        if not os.path.exists(self.model_save_path):
            os.mkdir(self.model_save_path)

        self.eps=1e-15#clip (eps,1-eps) | divide by zero.
        self.category_cols=[]
        self.weight_col='weight'#weight_col purged_CV
          
    #print colorful text
    def PrintColor(self,text:str='',color = Fore.BLUE)->None:
        print(color + text + Style.RESET_ALL)
    
    #save models after training
    def pickle_dump(self,obj, path:str)->None:
        #open path,binary write
        with open(path, mode="wb") as f:
            dill.dump(obj, f, protocol=4)
    #load models when inference
    def pickle_load(self,path:str):
        #open path,binary read
        with open(path, mode="rb") as f:
            data = dill.load(f)
            return data
        
    #Traverse all columns of df, modify data types to reduce memory usage
    def reduce_mem_usage(self,df:pd.DataFrame, float16_as32:bool=True)->pd.DataFrame:
        #memory_usage()是df每列的内存使用量,sum是对它们求和, B->KB->MB
        start_mem = df.memory_usage().sum() / 1024**2
        print('Memory usage of dataframe is {:.2f} MB'.format(start_mem))
        for col in df.columns:#遍历每列的列名
            col_type = df[col].dtype#列名的type
            if col_type != object and str(col_type)!='category':#不是object也就是说这里处理的是数值类型的变量
                c_min,c_max = df[col].min(),df[col].max() #求出这列的最大值和最小值
                if str(col_type)[:3] == 'int':#如果是int类型的变量,不管是int8,int16,int32还是int64
                    #如果这列的取值范围是在int8的取值范围内,那就对类型进行转换 (-128 到 127)
                    if c_min > np.iinfo(np.int8).min and c_max < np.iinfo(np.int8).max:
                        df[col] = df[col].astype(np.int8)
                    #如果这列的取值范围是在int16的取值范围内,那就对类型进行转换(-32,768 到 32,767)
                    elif c_min > np.iinfo(np.int16).min and c_max < np.iinfo(np.int16).max:
                        df[col] = df[col].astype(np.int16)
                    #如果这列的取值范围是在int32的取值范围内,那就对类型进行转换(-2,147,483,648到2,147,483,647)
                    elif c_min > np.iinfo(np.int32).min and c_max < np.iinfo(np.int32).max:
                        df[col] = df[col].astype(np.int32)
                    #如果这列的取值范围是在int64的取值范围内,那就对类型进行转换(-9,223,372,036,854,775,808到9,223,372,036,854,775,807)
                    elif c_min > np.iinfo(np.int64).min and c_max < np.iinfo(np.int64).max:
                        df[col] = df[col].astype(np.int64)  
                else:#如果是浮点数类型.
                    #如果数值在float16的取值范围内,如果觉得需要更高精度可以考虑float32
                    if c_min > np.finfo(np.float16).min and c_max < np.finfo(np.float16).max:
                        if float16_as32:#如果数据需要更高的精度可以选择float32
                            df[col] = df[col].astype(np.float32)
                        else:
                            df[col] = df[col].astype(np.float16)  
                    #如果数值在float32的取值范围内，对它进行类型转换
                    elif c_min > np.finfo(np.float32).min and c_max < np.finfo(np.float32).max:
                        df[col] = df[col].astype(np.float32)
                    #如果数值在float64的取值范围内，对它进行类型转换
                    else:
                        df[col] = df[col].astype(np.float64)
        #calculate memory after optimization
        end_mem = df.memory_usage().sum() / 1024**2
        print('Memory usage after optimization is: {:.2f} MB'.format(end_mem))
        print('Decreased by {:.1f}%'.format(100 * (start_mem - end_mem) / start_mem))
        return df
     
    def clean_text(self,text:str='')->str:
        ############################## fix text #######################################################
        #transform emoji to " "+text+" ".
        text=emoji.demojize(text,delimiters=(" ", " "))
        #correct unicode issues.
        text=ftfy.fix_text(text)
        #lower         example:'Big' and 'big'
        text=text.lower()
        ############################## remove meaningless text ########################################
        #remove <b>  <p> meaningless
        html=re.compile(r'<.*?>')
        text=html.sub(r'',text)
        #remove url '\w+':(word character,[a-zA-Z0-9_])
        text=re.sub("http\w+",'',text)
        #remove @yunsuxiaozi   person_name 
        text=re.sub("@\w+",'',text)
        #drop single character,they are meaningless. 'space a space'
        text=re.sub("\s[a-z]\s",'',text)
        #remove number
        #text=re.sub("\d+",'',text)
        #drop english stopwords,they are meaningless.
        english_stopwords = stopwords.words('english')
        text_list=text.split(" ")
        text_list=[t for t in text_list if t not in english_stopwords]
        text=" ".join(text_list)
        #drop space front and end.
        text=text.strip()
        return text

    #3 text readable index 
    def ARI(self,text):
        characters=len(text)
        words=len(re.split(' |\\n|\\.|\\?|\\!|\,',text))
        sentence=len(re.split('\\.|\\?|\\!',text))
        ari_score=4.71*(characters/words)+0.5*(words/sentence)-21.43
        return ari_score
    def McAlpine_EFLAW(self,text):
        W=len(re.split(' |\\n|\\.|\\?|\\!|\,',text))
        S=len(re.split('\\.|\\?|\\!',text))
        mcalpine_eflaw_score=(W+S*W)/S
        return mcalpine_eflaw_score
    def CLRI(self,text):
        characters=len(text)
        words=len(re.split(' |\\n|\\.|\\?|\\!|\,',text))#空格,换行符,句号,问号,感叹号,逗号分开.
        sentence=len(re.split('\\.|\\?|\\!',text))#句号,问号,感叹号分开的句子.
        L=100*characters/words
        S=100*sentence/words
        clri_score=0.0588*L-0.296*S-15.8
        return clri_score
         
    #basic Feature Engineer,mode='train' or 'test' ,drop_cols is other cols you want to delete.
    def base_FE(self,df:pd.DataFrame,mode:str='train',drop_cols:list[str]=[])->pd.DataFrame:
        if self.FE!=None:
            #use your custom metric first
            df=self.FE(df)
        #category columns
        for col in self.category_cols:
            #preprocessing
            df[col]=df[col].apply(lambda x:str(x).lower())
            df=self.label_encoder(df,label_encoder_cols=[col],fold=self.num_folds)
            df[col]=df[col].astype('category')
        
        #text feature extract,such as word,sentence,paragraph.
        #The reason why it needs to be done earlier is that it will generate columns such as nunique=1 or
        #object that need to be dropped, so it needs to be placed before finding these columns.
        if len(self.text_cols):
            print("< text column's feature >")
            df['index']=np.arange(len(df))
            for tcol in self.text_cols:  
                #data processing
                df[tcol]=(df[tcol].fillna('nan')).apply(lambda x:self.clean_text(x))
                df[tcol+"_ARI"]=df[tcol].apply(lambda x:self.ARI(x))
                df[tcol+"_CLRI"]=df[tcol].apply(lambda x:self.CLRI(x))
                df[tcol+"_McAlpine_EFLAW"]=df[tcol].apply(lambda x:self.McAlpine_EFLAW(x))
                #split by ps
                ps='!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~'
                for i in range(len(ps)):
                    df[tcol+f"split_ps{i}_count"]=df[tcol].apply(lambda x:len(x.split(ps[i])))
                
                self.PrintColor(f"-> for column {tcol} word feature",color=Fore.RED)
                tcol_word_df=df[['index',tcol]].copy()
                #get word_list   [index,tcol,word_list]
                tcol_word_df['word']=tcol_word_df[tcol].apply(lambda x: re.split('\\.|\\?|\\!\\ |\\,',x))
                #[index,single_word]
                tcol_word_df=tcol_word_df.explode('word')[['index','word']]
                #[index,single_word,single_word_len]
                tcol_word_df['word_len'] = tcol_word_df['word'].apply(len)
                #data clean [index,single_word,single_word_len]
                tcol_word_df=tcol_word_df[tcol_word_df['word_len']!=0]
                #for word features, extract the difference in length between the two words before and after.
                group_cols=['word_len']
                for gap in [1]:
                    for col in ['word_len']:
                        tcol_word_df[f'{col}_diff{gap}']=tcol_word_df.groupby(['index'])[col].diff(gap)
                        group_cols.append(f'{col}_diff{gap}')
                tcol_word_agg_df = tcol_word_df[['index']+group_cols].groupby(['index']).agg(self.AGGREGATIONS)
                tcol_word_agg_df.columns = ['_'.join(x) for x in tcol_word_agg_df.columns]
                df=df.merge(tcol_word_agg_df,on='index',how='left')
                
                self.PrintColor(f"-> for column {tcol} sentence feature",color=Fore.RED)
                tcol_sent_df=df[['index',tcol]].copy()
                #get sent_list   [index,tcol,sent_list]
                tcol_sent_df['sent']=tcol_sent_df[tcol].apply(lambda x: re.split('\\.|\\?|\\!',x))
                #[index,single_sent]
                tcol_sent_df=tcol_sent_df.explode('sent')[['index','sent']]
                #[index,single_sent,single_sent_len]
                tcol_sent_df['sent_len'] = tcol_sent_df['sent'].apply(len)
                tcol_sent_df['sent_word_count'] = tcol_sent_df['sent'].apply(lambda x:len(re.split('\\ |\\,',x)))
                #data clean [index,single_sent,single_sent_len]
                group_cols=['sent_len','sent_word_count']
                for gcol in group_cols:
                    tcol_sent_df=tcol_sent_df[tcol_sent_df[gcol]!=0]
                #for sent features, extract the difference in length between the two sents before and after.
                for gap in [1]:
                    for col in ['sent_len','sent_word_count']:
                        tcol_sent_df[f'{col}_diff{gap}']=tcol_sent_df.groupby(['index'])[col].diff(gap)
                        group_cols.append(f'{col}_diff{gap}')
                tcol_sent_agg_df = tcol_sent_df[['index']+group_cols].groupby(['index']).agg(self.AGGREGATIONS)
                tcol_sent_agg_df.columns = ['_'.join(x) for x in tcol_sent_agg_df.columns]
                df=df.merge(tcol_sent_agg_df,on='index',how='left')
                
                self.PrintColor(f"-> for column {tcol} paragraph feature",color=Fore.RED)
                tcol_para_df=df[['index',tcol]].copy()
                #get para_list   [index,tcol,para_list]
                tcol_para_df['para']=tcol_para_df[tcol].apply(lambda x: x.split("\n"))
                #[index,single_para]
                tcol_para_df=tcol_para_df.explode('para')[['index','para']]
                tcol_para_df['para_len'] = tcol_para_df['para'].apply(len)
                tcol_para_df['para_sent_count'] = tcol_para_df['para'].apply(lambda x: len(re.split('\\.|\\?|\\!',x)))
                tcol_para_df['para_word_count'] = tcol_para_df['para'].apply(lambda x: len(re.split('\\.|\\?|\\!\\ |\\,',x)))
                #data clean [index,single_sent,single_sent_len]
                group_cols=['para_len','para_sent_count','para_word_count']
                for gcol in group_cols:
                    tcol_para_df=tcol_para_df[tcol_para_df[gcol]!=0]
                #for sent features, extract the difference in length between the two sents before and after.
                for gap in [1]:
                    for col in ['para_len','para_sent_count','para_word_count']:
                        tcol_para_df[f'{col}_diff{gap}']=tcol_para_df.groupby(['index'])[col].diff(gap)
                        group_cols.append(f'{col}_diff{gap}')
                tcol_para_agg_df = tcol_para_df[['index']+group_cols].groupby(['index']).agg(self.AGGREGATIONS)
                tcol_para_agg_df.columns = ['_'.join(x) for x in tcol_para_agg_df.columns]
                df=df.merge(tcol_para_agg_df,on='index',how='left') 
            df.drop(['index'],axis=1,inplace=True)
        
        if mode=='train':
            #missing value 
            self.nan_cols=[col for col in df.columns if df[col].isna().mean()>self.nan_margin]
            #nunique=1
            self.unique_cols=[col for col in df.drop(self.drop_cols+self.list_cols+[self.weight_col],axis=1,errors='ignore').columns if(df[col].nunique()==1)]
            #object dtype
            self.object_cols=[col for col in df.drop(self.drop_cols+self.category_cols,axis=1,errors='ignore').columns if (df[col].dtype==object) and (col not in [self.group_col,self.target_col])]
            #one_hot_cols
            self.one_hot_cols=[]
            self.nunique_2_cols=[]
            for col in df.columns:
                if col not in [self.target_col,self.group_col,self.weight_col]+self.list_cols+self.category_cols+self.drop_cols:
                    if (df[col].nunique()<self.one_hot_max) and (df[col].nunique()>2):
                        self.one_hot_cols.append([col,list(df[col].unique())]) 
                    elif (self.one_hot_max>=2) and (df[col].nunique()==2):
                        self.nunique_2_cols.append([col,list(df[col].unique())[0]])
        if self.one_hot_max>1:
            print("< one hot encoder >")          
            for i in range(len(self.one_hot_cols)):
                col,nunique=self.one_hot_cols[i]
                for u in nunique:
                    df[f"{col}_{u}"]=(df[col]==u).astype(np.int8)
                #one_hot_value_count
                try:
                    col_valuecounts=self.onehot_valuecounts[col]
                except:
                    col_valuecounts=df[col].value_counts().to_dict()
                    self.onehot_valuecounts[col]=col_valuecounts
                df[col+"_valuecounts"]=df[col].apply(lambda x:col_valuecounts.get(x,np.nan))
                df[col+"_valuecounts"]=df[col+"_valuecounts"].apply(lambda x:np.nan if x<5 else x)
                
            for i in range(len(self.nunique_2_cols)):
                c,u=self.nunique_2_cols[i]
                df[f"{c}_{u}"]=(df[c]==u).astype(np.int8)
        
        if len(self.list_cols):
            print("< list column's feature >")
            for col in self.list_cols:
                try:#if str(list),transform '[a,b]' to [a,b]
                    df[col]=df[col].apply(lambda x:ast.literal_eval(x))
                except:#origin data is list or data can't be parsed.
                    if not isinstance(df[col].dropna().values[0],list):
                        raise ValueError(f"col '{col}' not a list.")
                
                #add index,data of list can groupby index.
                df['index']=np.arange(len(df))
                #construct origin feats 
                list_col_df=df.copy().explode(col)[['index',col]]

                group_cols=[col]
                for gap in self.list_gaps:
                    self.PrintColor(f"-> for column {col} gap{gap}",color=Fore.RED)
                    list_col_df[f"{col}_gap{gap}"]=list_col_df.groupby(['index'])[col].diff(gap)
                    group_cols.append( f"{col}_gap{gap}" )

                list_col_agg_df = list_col_df[['index']+group_cols].groupby(['index']).agg(self.AGGREGATIONS)
                list_col_agg_df.columns = ['_'.join(x) for x in list_col_agg_df.columns]
                df=df.merge(list_col_agg_df,on='index',how='left')
                df[f'{col}_len']=df[col].apply(len)
                
                for gcol in group_cols:
                    df[f'{gcol}_ptp']=df[f'{gcol}_max']-df[f'{gcol}_min']
                    df[f'{gcol}_mean/{gcol}_std']=df[f'{gcol}_mean']/(df[f'{gcol}_std']+self.eps)

                col_list=df[col].values
                max_k=10
                res=[]
                for i in range(len(df)):
                    #{1:count2,2:count4,3:count1}
                    vs,cs = np.unique(col_list[i], return_counts=True)
                    res_=[]
                    for k in range(max_k):
                        res_.append(np.sum(cs==k+1))
                    res.append(res_)
                res=np.array(res)
                for k in range(max_k):
                    df[f"{col}_valuecount_equal{k+1}_cnt"]=res[:,k]
                
                #drop index after using.
                df.drop(['index'],axis=1,inplace=True)
        
        if len(self.word2vec_models):#word2vec transform
            self.word2vec_cols=[]
            for (model,col,model_name) in self.word2vec_models:
                self.word2vec_cols.append(col)
            #set to duplicate removal
            self.word2vec_cols=list(set(self.word2vec_cols))
           
        if (mode=='train') and (self.use_high_corr_feat==False):#drop high correlation features
            print("< drop high correlation feature >")
            self.drop_high_correlation_feats(df)
       
        if len(self.cross_cols)!=0:
            print("< cross feature >")
            for i in range(len(self.cross_cols)):
                for j in range(i+1,len(self.cross_cols)):
                    df[self.cross_cols[i]+"+"+self.cross_cols[j]]=df[self.cross_cols[i]]+df[self.cross_cols[j]]
                    df[self.cross_cols[i]+"-"+self.cross_cols[j]]=df[self.cross_cols[i]]-df[self.cross_cols[j]]
                    df[self.cross_cols[i]+"*"+self.cross_cols[j]]=df[self.cross_cols[i]]*df[self.cross_cols[j]]
                    df[self.cross_cols[i]+"/"+self.cross_cols[j]]=df[self.cross_cols[i]]/(df[self.cross_cols[j]]+self.eps)
        
        print("< drop useless cols >")
        total_drop_cols=self.nan_cols+self.unique_cols+self.object_cols+drop_cols
        total_drop_cols=[col for col in total_drop_cols if col not in self.word2vec_cols+self.labelencoder_cols]
        df.drop(total_drop_cols,axis=1,inplace=True,errors='ignore')
        if self.use_reduce_memory:
            df=self.reduce_mem_usage(df,float16_as32=True)
        print("-"*30)
        return df

    def label_encoder(self,df,label_encoder_cols,fold):
        for col in label_encoder_cols:
            try:
                self.PrintColor(f"-> for column {self.name2col[col]} labelencoder feature",color=Fore.RED)
            except:
                self.PrintColor(f"-> for column {col} labelencoder feature",color=Fore.RED)
            #load model when model is existed,fit when model isn't exist.
            try:
                le=self.trained_le[f'le_{col}_fold{fold}.model']
            except:#training
                value=df[col].value_counts().to_dict()
                le={}
                for k,v in value.items():
                    le[k]=len(le)
                self.pickle_dump(le,self.model_save_path+f'le_{col}_fold{fold}.model')
                self.trained_le[f'le_{col}_fold{fold}.model']=copy.deepcopy(le)
            df[col] = df[col].apply(lambda x:le.get(x,0))
        return df
    
    #Feature engineering that needs to be done internally in cross validation.
    def CV_FE(self,df:pd.DataFrame,mode:str='train',fold:int=0)->pd.DataFrame:
        #labelencoder
        if len(self.labelencoder_colnames):
            print("< label encoder >")
            df=self.label_encoder(df,label_encoder_cols=self.labelencoder_colnames,fold=fold)

        if len(self.word2vec_models):
            print("< word2vec >")
            for (word2vec,col,model_name) in self.word2vec_models:
                self.PrintColor(f"-> for column {col} {model_name} word2vec feature",color=Fore.RED)
                col=self.col2name[col]
                df[col]=df[col].fillna('nan')
                #load when model is existed.fit when model isn't existed.
                try:
                    word2vec=self.trained_wordvec[f'{model_name}_{col}_fold{fold}.model' ]
                except:
                    word2vec.fit(df[col].apply( lambda x: self.clean_text(x)  )  )
                    self.pickle_dump(word2vec,self.model_save_path+f'{model_name}_{col}_fold{fold}.model') 
                    self.trained_wordvec[f'{model_name}_{col}_fold{fold}.model' ]=copy.deepcopy(word2vec)
                word2vec_feats=word2vec.transform(df[col].apply(lambda x: self.clean_text(x)  )).toarray()
                for i in range(word2vec_feats.shape[1]):
                    df[f"{col}_{model_name}_{i}"]=word2vec_feats[:,i]
        df.drop(self.word2vec_colnames+self.labelencoder_colnames,axis=1,inplace=True)
        #after this operation,df will be dropped into model,so we need to Convert object to floating-point numbers
        for col in df.columns:
            if (df[col].dtype==object):
                df[col]=df[col].astype(np.float32)
        #replace inf to nan
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        #xgboost treat -1 as missing value.
        num_cols=[col for col in df.columns if str(df[col].dtype) not in ['category','object','string']]
        df[num_cols]=df[num_cols].fillna(-1)
        return df  
    
    def Metric(self,y_true:np.array,y_pred=np.array)->float:#for multi_class,labeland proability
        #use cutom_metric when you define.
        if self.custom_metric!=None:
            return self.custom_metric(y_true,y_pred)
        if self.objective=='regression':
            if self.metric=='medae':
                return np.median(np.abs(y_true-y_pred))
            elif self.metric=='mae':
                return np.mean(np.abs(y_true-y_pred))
            elif self.metric=='rmse':
                return np.sqrt(np.mean((y_true-y_pred)**2))
            elif self.metric=='mse':
                return np.mean((y_true-y_pred)**2)
            elif self.metric=='rmsle':
                return np.sqrt(np.mean((np.log1p(y_pred)-np.log1p(y_true))**2))
            elif self.metric=='msle':
                return np.mean((np.log1p(y_pred)-np.log1p(y_true))**2)
            elif self.metric=='mape':
                return np.mean(np.abs(y_pred-y_true)/y_true)
            elif self.metric=='r2':
                return 1-np.sum ((y_true-y_pred)**2)/np.sum ((y_true-np.mean(y_true))**2)
        else:
            if self.metric=='accuracy':
                y_pred=np.argmax(y_pred,axis=1)#transform probability to label
                return np.mean(y_true==y_pred)
            elif self.metric=='auc':
                return roc_auc_score(y_true,y_pred[:,1])
            elif self.metric=='f1_score':
                y_pred=np.argmax(y_pred,axis=1)#transform probability to label
                return f1_score(y_true, y_pred)
            elif self.metric=='mcc':
                y_pred=np.argmax(y_pred,axis=1)#transform probability to label
                return matthews_corrcoef(y_true, y_pred)
            elif self.metric in ['logloss','multi_logloss']:
                y_true=np.eye(self.num_classes)[y_true]
                y_pred=np.clip(y_pred,self.eps,1-self.eps)
                return -np.mean(np.sum(y_true*np.log(y_pred),axis=-1))
    
    def optuna_lgb(self,X:pd.DataFrame,y:pd.DataFrame,group,kf_folds:pd.DataFrame,metric:str)->dict:
        def objective(trial):
            params = {
                "boosting_type": "gbdt","metric": metric,
                'random_state': self.seed,
                'n_estimators': trial.suggest_int('n_estimators', 500,1500),
                'reg_alpha': trial.suggest_loguniform('reg_alpha', 1e-3, 10.0),
                'reg_lambda': trial.suggest_loguniform('reg_lambda', 1e-3, 10.0),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1),
                'subsample': trial.suggest_float('subsample', 0.5, 1),
                'learning_rate': trial.suggest_float('learning_rate', 1e-4, 0.5, log=True),
                'num_leaves' : trial.suggest_int('num_leaves', 8, 64),
                'min_child_samples': trial.suggest_int('min_child_samples', 2, 100),
                "extra_trees":True,
                "verbose": -1
            }
            if self.device in ['cuda','gpu']:#gpu mode when training
                params['device']='gpu'
                params['gpu_use_dp']=True
            model_name='lgb'
            if self.objective=='regression':
                model=LGBMRegressor(**params)
            else:
                model=LGBMClassifier(**params)   
            oof_preds,metric_score=self.cross_validation(X=X,y=y,group=group,kf_folds=kf_folds,model=model,model_name=model_name,sample_weight=self.sample_weight,use_optuna=True)
            return metric_score
        
        #direction is 'minimize' or 'maximize'
        direction=self.optuna_direction
        for key in self.direction2metric.keys():
            if self.metric in self.direction2metric[key]:
                direction=key
            
        study = optuna.create_study(direction=direction, study_name='find best lgb_params') 
        study.optimize(objective, n_trials=self.use_optuna_find_params)
        best_params=study.best_trial.params
        best_params["boosting_type"]="gbdt"
        best_params["extra_trees"]=True
        best_params["metric"]=metric
        best_params['random_state']=self.seed
        best_params['verbose']=-1
        print(f"best_params={best_params}")
        return best_params

    def load_data(self,path_or_file:str|pd.DataFrame|pl.DataFrame='train.csv',mode:str='train')->None|pd.DataFrame:
        if mode=='train':
            #read csv,parquet or csv_file
            self.train_path_or_file=path_or_file
        
        if type(path_or_file)==str:#path
            if path_or_file[-4:]=='.csv':
                file=pl.read_csv(path_or_file)
            elif path_or_file[-8:]=='.parquet':
                file=pl.read_parquet(path_or_file)
            try:#if load csv or parquet file
                file=file.to_pandas()
            except:
                raise ValueError("Yunbase can only support csv file or parquet file")
        else:#file
            file=path_or_file.copy()
            #polars to pandas.
            if isinstance(file, pl.DataFrame):
                file=file.to_pandas()
            if not isinstance(file, pd.DataFrame):
                raise ValueError(f"{mode}_path_or_file is not pd.DataFrame.")
                
        if mode=='train':
            self.train=file.copy()
        elif mode=='test':
            self.test=file.copy()
        else:#submission.csv
            return file

    #https://www.kaggle.com/code/marketneutral/purged-time-series-cv-xgboost-optuna
    def purged_cross_validation(self,train_path_or_file:str|pd.DataFrame|pl.DataFrame='train.csv',
                                test_path_or_file:str|pd.DataFrame|pl.DataFrame='test.csv',
                                date_col:str='date',train_gap_each_fold:int=31,#one month
                                train_test_gap:int=7,#a week
                                train_date_range:int=0,test_date_range:int=0,
                                category_cols:list[str]=[],
                                weight_col:str='weight',
                               ):
        if self.use_pseudo_label:
            raise ValueError("purged CV can't support use pseudo label.")
        if self.group_col!=None:
            raise ValueError("purged CV can't support groupkfold.")
        if len(self.models)==0:
            raise ValueError("len(models) can't be 0.")
        if (self.use_optuna_find_params!=0) or (self.optuna_direction!=None):
            raise ValueError("purged CV can't support optuna find params.")
        self.load_data(path_or_file=train_path_or_file,mode='train')
        self.load_data(path_or_file=test_path_or_file,mode='test')
        self.date_col=date_col
        self.weight_col=weight_col
        if self.weight_col not in list(self.train.columns):
            self.train[self.weight_col]=1
        
        self.category_cols=category_cols
        self.target_dtype=self.train[self.target_col].dtype
        if self.objective!='regression':#check target
            unique_target=sorted(self.train[self.target_col].unique())
            if unique_target!=list(np.arange(len(unique_target))):
                raise ValueError(f"purged CV can only support target from 0 to {len(unique_target)-1}")
        print("< preprocess date_col >")
        try:#if df[date_col] is string such as '2024-11-08'
            #transform date to datetime
            if type(self.train.dropna()[self.date_col].values[0])==str:
                self.train[self.date_col]=pd.to_datetime(self.train[self.date_col])
            if type(self.test.dropna()[self.date_col].values[0])==str:
                self.test[self.date_col]=pd.to_datetime(self.test[self.date_col])
            #transform 'date' to days.
            min_date=self.train[self.date_col].min()
            self.train[self.date_col]=(self.train[self.date_col]-min_date).dt.days
            self.test[self.date_col]=(self.test[self.date_col]-min_date).dt.days
        except:#df[date_col] is [0,1,2,……,n]
            min_date=self.train[self.date_col].min()
            self.train[self.date_col]=self.train[self.date_col]-min_date
            self.test[self.date_col]=self.test[self.date_col]-min_date

        if test_date_range==0:#date_range same as test_data
            test_date_range=self.test[self.date_col].max()-self.test[self.date_col].min()+1
        if train_date_range==0:
           a=self.train[self.date_col].max()+1-(self.num_folds-1)*train_gap_each_fold-train_test_gap-test_date_range
           b=self.train[self.date_col].max()+1-self.num_folds*train_gap_each_fold-train_test_gap 
           train_date_range=min(a,b)
        #last fold out of index?
        assert (self.num_folds-1)*train_gap_each_fold+train_date_range+train_test_gap+test_date_range<=self.train[self.date_col].max()+1
        #final train set out of index?
        assert self.num_folds*train_gap_each_fold+train_date_range+train_test_gap <=self.train[self.date_col].max()+1

        self.train=self.base_FE(self.train,mode='train',drop_cols=self.drop_cols)
        self.test=self.base_FE(self.test,mode='test',drop_cols=self.drop_cols)

        print("< date col FE >")# not use onehot encoder for these columns
        self.train['day']=self.train[self.date_col]%365
        self.train['dayofweek']=self.train[self.date_col]%7
        self.train['month']=self.train[self.date_col]%31
        self.train['sin_dayofweek']=np.sin(2*np.pi*self.train['dayofweek']/7)
        self.train['cos_dayofweek']=np.cos(2*np.pi*self.train['dayofweek']/7)
        self.train['sin_day']=np.sin(2*np.pi*self.train['day']/365)
        self.train['cos_day']=np.cos(2*np.pi*self.train['day']/365)
        self.train['sin_month']=np.sin(2*np.pi*self.train['month']/31)
        self.train['cos_month']=np.cos(2*np.pi*self.train['month']/31)

        self.test['day']=self.test[self.date_col]%365
        self.test['dayofweek']=self.test[self.date_col]%7
        self.test['month']=self.test[self.date_col]%31
        self.test['sin_dayofweek']=np.sin(2*np.pi*self.test['dayofweek']/7)
        self.test['cos_dayofweek']=np.cos(2*np.pi*self.test['dayofweek']/7)
        self.test['sin_day']=np.sin(2*np.pi*self.test['day']/365)
        self.test['cos_day']=np.cos(2*np.pi*self.test['day']/365)
        self.test['sin_month']=np.sin(2*np.pi*self.test['month']/31)
        self.test['cos_month']=np.cos(2*np.pi*self.test['month']/31)

        #use origin columns
        self.word2vec_colnames=self.word2vec_cols
        self.labelencoder_colnames=self.labelencoder_cols
        self.col2name={}
        self.name2col={}
        train_columns=list(self.train.columns)
        for i in range(len(train_columns)):
            self.col2name[train_columns[i]]=train_columns[i]
            self.name2col[train_columns[i]]=train_columns[i]
        
        self.PrintColor("purged CV")
        for (model,model_name) in self.models:
            print(f"{model_name}_params={model.get_params()}")
        for model,model_name in self.models:
            CV_score=[]
            for fold in range(self.num_folds):
                print(f"fold {fold},model_name:{model_name}")
                train_date_min=fold*train_gap_each_fold
                train_date_max=train_date_min+train_date_range
                test_date_min=train_date_max+train_test_gap
                test_date_max=test_date_min+test_date_range
                print(f"train_date_min:{train_date_min},train_date_max:{train_date_max}")
                print(f"test_date_min:{test_date_min},test_date_max:{test_date_max}")
                train_fold=self.train.copy()[(self.train[self.date_col]>=train_date_min)&(self.train[self.date_col]<=train_date_max)]
                valid_fold=self.train.copy()[(self.train[self.date_col]>=test_date_min)&(self.train[self.date_col]<=test_date_max)]
                X_train=train_fold.drop([self.target_col,self.date_col,self.weight_col],axis=1)
                train_weight=train_fold[self.weight_col]
                y_train=train_fold[self.target_col]
                X_valid=valid_fold.drop([self.target_col,self.date_col,self.weight_col],axis=1)
                y_valid=valid_fold[self.target_col]

                X_train=self.CV_FE(X_train,mode='train',fold=fold)
                X_valid=self.CV_FE(X_valid,mode='test',fold=fold)

                if self.exp_mode:#use log transform for target_col
                    self.exp_mode_b=-y_train.min()
                    y_train=np.log1p(y_train+self.exp_mode_b)
                
                #don't use early_stop,because final_trainset don't have valid_set.
                if 'lgb' in model_name:
                     #gpu params isn't set
                    if self.device in ['cuda','gpu']:#gpu mode when training
                        params=model.get_params()
                        if (params.get('device',-1)==-1) or (params.get('gpu_use_dp',-1)==-1):
                             raise ValueError("The 'device' of lightgbm is 'gpu' and 'gpu_use_dp' must be True.")
                    model.fit(X_train, y_train,eval_set=[(X_valid, y_valid)],
                              sample_weight=train_weight,
                              callbacks=[log_evaluation(self.log)])
                elif 'xgb' in model_name:
                    #gpu params isn't set
                    if self.device in ['cuda','gpu']:#gpu mode when training
                        params=model.get_params()
                        if (params.get('tree_method',-1)!='gpu_hist'):
                             raise ValueError("The 'tree_method' of xgboost must be 'gpu_hist'.")
                    model.fit(X_train,y_train,eval_set=[(X_valid, y_valid)],
                              sample_weight=train_weight,
                              verbose=self.log)
                elif 'cat' in model_name:
                    #gpu params isn't set
                    if self.device in ['cuda','gpu']:#gpu mode when training
                        params=model.get_params()
                        if (params.get('task_type',-1)==-1):
                             raise ValueError("The 'task_type' of catboost must be 'GPU'.")
                    X_train[self.category_cols]=X_train[self.category_cols].astype('string')
                    X_valid[self.category_cols]=X_valid[self.category_cols].astype('string')
                    model.fit(X_train,y_train, eval_set=(X_valid, y_valid),
                              sample_weight=train_weight,
                              cat_features=self.category_cols,
                              verbose=self.log)
                elif 'tabnet' in model_name:
                    cat_idxs,cat_dims=[],[]
                    X_train_columns=list(X_train.columns)
                    for idx in range(len(X_train_columns)):
                        if X_train[X_train_columns[idx]].dtype=='category':
                            cat_idxs.append(idx)
                            cat_dims.append(train[X_train_columns[idx]].nunique())
                            X_train[X_train_columns[idx]]=X_train[X_train_columns[idx]].apply(lambda x:int(x)).astype(np.int32)          
                    params=model.get_params()
                    params['cat_idxs']=cat_idxs
                    params['cat_dims']=cat_dims
                    params['cat_emb_dim']=[5]*len(cat_idxs)
                    if self.objective=='regression':
                        model=TabNetRegressor(**params)
                        model.fit(
                            X_train.to_numpy(), y_train.to_numpy().reshape(-1,1),
                            eval_metric=['rmse'],
                            batch_size=1024,
                        )
                    else:
                        model=TabNetClassifier(**params)
                        model.fit(
                            X_train.to_numpy(), y_train.to_numpy(),
                            batch_size=1024,
                        )
                else:
                    model.fit(X_train,y_train)
                #print feature importance when not use optuna to find params.
                if self.plot_feature_importance:
                    #can only support GBDT.
                    if ('lgb' in model_name) or ('xgb' in model_name) or ('cat' in model_name):
                        origin_features=[]
                        for col in X_train.columns:
                            try:#named 'col_1' when training
                                origin_features.append(self.name2col[col])
                            except:#tfidf feature
                                origin_features.append(col)
                            
                        feature_importance=model.feature_importances_
                        #convert to percentage
                        feature_importance=feature_importance/np.sum(feature_importance)
                        feat_import_dict={k:v for k,v in zip(origin_features,feature_importance)}
                        feat_import_dict={k:v for k,v in sorted(feat_import_dict.items(),key=lambda x:-x[1])}
                        self.pickle_dump(feat_import_dict,self.model_save_path+f'{model_name}_fold{fold}_feature_importance.pkl')
                        bestk,worstk=min(10,int(len(origin_features)*0.1+1)),min(10,int(len(origin_features)*0.1+1))
                        print(f"top{bestk} best features is :{list(feat_import_dict.keys())[:bestk]}")
                        print(f"top{worstk} worst features is :{list(feat_import_dict.keys())[-worstk:]}")
    
                        #plot feature importance
                        plt.figure(figsize = (12, 2*bestk/5))
                        sns.barplot(
                            y=list(feat_import_dict.keys())[:bestk],
                            x=list(feat_import_dict.values())[:bestk],
                        )
                        plt.title(f"{model_name} fold {fold} top{bestk} best Feature Importance")
                        plt.show()
                if self.objective=='regression':
                    valid_pred=self.predict_batch(model=model,test_X=X_valid)
                else:
                    valid_pred=self.predict_proba_batch(model=model,test_X=X_valid)
                if self.exp_mode:
                    valid_pred=np.expm1(valid_pred)-self.exp_mode_b
                if self.save_oof_preds:#if oof_preds is needed
                    np.save(self.model_save_path+f"{model_name}_seed{self.seed}_fold{fold}.npy",y_valid.values)
                    np.save(self.model_save_path+f"{model_name}_seed{self.seed}_fold{fold}.npy",valid_pred)
                
                CV_score.append(self.Metric(y_valid,valid_pred))
                
                del X_train,y_train,X_valid,y_valid,valid_pred
                gc.collect()
                
                print(f"{self.metric}:{CV_score[-1]}")
            self.PrintColor(f"mean_{self.metric}------------------------------>{np.mean(CV_score)}",color = Fore.RED)
        
        self.PrintColor("prediction on test data")
        train_date_min=self.train[self.date_col].max()-train_test_gap-train_date_range
        train_date_max=self.train[self.date_col].max()-train_test_gap
        print(f"train_date_min:{train_date_min},train_date_max:{train_date_max}")
        train=self.train[(self.train[self.date_col]>=train_date_min)&(self.train[self.date_col]<=train_date_max)]
        train_weight=train[self.weight_col]
        X_train=train.drop([self.target_col,self.date_col,self.weight_col],axis=1)
        y_train=train[self.target_col]
        if self.exp_mode:#use log transform for target_col
            self.exp_mode_b=-y_train.min()
            y_train=np.log1p(y_train+self.exp_mode_b)
        test_X=self.test.drop([self.date_col],axis=1)

        X_train=self.CV_FE(X_train,mode='train',fold=self.num_folds)
        test_X=self.CV_FE(test_X,mode='test',fold=self.num_folds)
        
        test_preds=[]
        for model,model_name in self.models:
            #don't use early_stop,because final_trainset don't have valid_set.
            if 'lgb' in model_name:
                model.fit(X_train, y_train,sample_weight=train_weight,
                          callbacks=[log_evaluation(self.log)])
            elif 'xgb' in model_name:
                model.fit(X_train,y_train,sample_weight=train_weight,
                          verbose=self.log)
            elif 'cat' in model_name:
                X_train[self.category_cols]=X_train[self.category_cols].astype('string')
                model.fit(X_train,y_train, cat_features=self.category_cols,
                          sample_weight=train_weight,
                          verbose=self.log)
            elif 'tabnet' in model_name:
                cat_idxs,cat_dims=[],[]
                X_train_columns=list(X_train.columns)
                for idx in range(len(X_train_columns)):
                    if X_train[X_train_columns[idx]].dtype=='category':
                        cat_idxs.append(idx)
                        cat_dims.append(train[X_train_columns[idx]].nunique())
                        X_train[X_train_columns[idx]]=X_train[X_train_columns[idx]].apply(lambda x:int(x)).astype(np.int32)      
                         
                params=model.get_params()
                params['cat_idxs']=cat_idxs
                params['cat_dims']=cat_dims
                params['cat_emb_dim']=[5]*len(cat_idxs)

                if self.objective=='regression':
                    model=TabNetRegressor(**params)
                    model.fit(
                            X_train.to_numpy(), y_train.to_numpy().reshape(-1,1),
                            eval_metric=['rmse'],
                            batch_size=1024,
                        )
                else:
                    model=TabNetClassifier(**params)
                    model.fit(
                            X_train.to_numpy(), y_train.to_numpy(),
                            batch_size=1024,
                        )
            else:
                model.fit(X_train,y_train)
            if self.objective=='regression':
                test_pred=self.predict_batch(model=model,test_X=test_X)
            else:
                test_pred=self.predict_proba_batch(model=model,test_X=test_X)
            test_preds.append(test_pred)
        test_preds=np.mean(test_preds,axis=0)
        if self.save_test_preds:#True
            np.save(self.model_save_path+'test_preds.npy',test_preds)
        if self.objective!='regression':
            if self.metric=='auc':
                test_preds=test_preds[:,1]
            else:
                test_preds=np.argmax(test_preds,axis=1)
        if self.exp_mode:
            test_preds=np.expm1(test_preds)-self.exp_mode_b
        return test_preds
    
    # return oof_preds and metric_score
    # can use optuna to find params.If use optuna,then not save models.
    def cross_validation(self,X:pd.DataFrame,y:pd.DataFrame,group,kf_folds:pd.DataFrame,model,model_name,sample_weight,use_optuna):
        log=self.log
        if use_optuna:
            log=10000
        if self.objective=='regression':
            oof_preds=np.zeros(len(y))
        else:
            oof_preds=np.zeros((len(y),self.num_classes))
        for fold in range(self.num_folds):
            train_index=kf_folds[kf_folds['fold']!=fold].index
            valid_index=kf_folds[kf_folds['fold']==fold].index
            print(f"name:{model_name},fold:{fold}")

            X_train, X_valid = X.iloc[train_index].reset_index(drop=True), X.iloc[valid_index].reset_index(drop=True)
            y_train, y_valid = y.iloc[train_index].reset_index(drop=True), y.iloc[valid_index].reset_index(drop=True)

            X_train=self.CV_FE(X_train,mode='train',fold=fold)
            X_valid=self.CV_FE(X_valid,mode='test',fold=fold)

            sample_weight_train=sample_weight[train_index]
            
            if (self.use_pseudo_label) and (type(self.test)==pd.DataFrame):
                test_copy=self.CV_FE(self.test.copy(),mode='test',fold=fold)
                test_X=test_copy.drop([self.group_col,self.target_col],axis=1,errors='ignore')
                test_y=test_copy[self.target_col]
                #concat will transform 'category' to 'object'
                X_train=pd.concat((X_train,test_X),axis=0)
                X_train[self.categoryname]=X_train[self.categoryname].astype('category')
                y_train=pd.concat((y_train,test_y),axis=0)
                sample_weight_train=np.ones(len(X_train))

            if 'lgb' in model_name:
                #gpu params isn't set
                if self.device in ['cuda','gpu']:#gpu mode when training
                    params=model.get_params()
                    if (params.get('device',-1)==-1) or (params.get('gpu_use_dp',-1)==-1):
                         raise ValueError("The 'device' of lightgbm is 'gpu' and 'gpu_use_dp' must be True.")
                model.fit(X_train,y_train,eval_set=[(X_valid, y_valid)],
                         sample_weight=sample_weight_train,
                         categorical_feature=self.categoryname,
                         callbacks=[log_evaluation(log),early_stopping(self.early_stop)]
                    )
            elif 'cat' in model_name:
                #gpu params isn't set
                if self.device in ['cuda','gpu']:#gpu mode when training
                    params=model.get_params()
                    if (params.get('task_type',-1)==-1):
                         raise ValueError("The 'task_type' of catboost must be 'GPU'.")
                X_train[self.categoryname]=X_train[self.categoryname].astype('string')
                X_valid[self.categoryname]=X_valid[self.categoryname].astype('string')
                model.fit(X_train, y_train,
                      eval_set=(X_valid, y_valid),
                      cat_features=self.categoryname,
                      sample_weight=sample_weight_train,
                      early_stopping_rounds=self.early_stop, verbose=log)
            elif 'xgb' in model_name:
                #gpu params isn't set
                if self.device in ['cuda','gpu']:#gpu mode when training
                    params=model.get_params()
                    if (params.get('tree_method',-1)!='gpu_hist'):
                         raise ValueError("The 'tree_method' of xgboost must be 'gpu_hist'.")
                model.fit(X_train,y_train,eval_set=[(X_valid, y_valid)],
                          sample_weight=sample_weight_train,verbose=log)
            elif 'tabnet' in model_name:
                 cat_idxs,cat_dims=[],[]
                 X_train_columns=list(X_train.columns)
                 for idx in range(len(X_train_columns)):
                     if X_train[X_train_columns[idx]].dtype=='category':
                         cat_idxs.append(idx)
                         cat_dims.append(X[X_train_columns[idx]].nunique())
                         X_train[X_train_columns[idx]]=X_train[X_train_columns[idx]].apply(lambda x:int(x)).astype(np.int32)      
                         X_valid[X_train_columns[idx]]=X_valid[X_train_columns[idx]].apply(lambda x:int(x)).astype(np.int32)      
                 params=model.get_params()
                 params['cat_idxs']=cat_idxs
                 params['cat_dims']=cat_dims
                 params['cat_emb_dim']=[5]*len(cat_idxs)
                 if self.objective=='regression':
                     model=TabNetRegressor(**params)
                     model.fit(
                        X_train.to_numpy(), y_train.to_numpy().reshape(-1,1),
                        eval_metric=['rmse'],
                        eval_set=[(X_valid.to_numpy(), y_valid.to_numpy().reshape(-1,1) ) ],
                        batch_size=1024,
                    )
                 else:
                     model=TabNetClassifier(**params)
                     model.fit(
                        X_train.to_numpy(), y_train.to_numpy(),
                        eval_set=[(X_valid.to_numpy(), y_valid.to_numpy())],
                        batch_size=1024,
                    )
            else:#other models such as ridge,LinearRegression
                model.fit(X_train,y_train) 

            #print feature importance when not use optuna to find params.
            if (use_optuna==False) and (self.plot_feature_importance):
                #can only support GBDT.
                if ('lgb' in model_name) or ('xgb' in model_name) or ('cat' in model_name):
                    origin_features=[]
                    for col in X_train.columns:
                        try:#named 'col_1' when training
                            origin_features.append(self.name2col[col])
                        except:#tfidf feature
                            origin_features.append(col)
                            
                    feature_importance=model.feature_importances_
                    #convert to percentage
                    feature_importance=feature_importance/np.sum(feature_importance)
                    feat_import_dict={k:v for k,v in zip(origin_features,feature_importance)}
                    feat_import_dict={k:v for k,v in sorted(feat_import_dict.items(),key=lambda x:-x[1])}
                    self.pickle_dump(feat_import_dict,self.model_save_path+f'{model_name}_fold{fold}_feature_importance.pkl')
                    bestk,worstk=min(10,int(len(origin_features)*0.1+1)),min(10,int(len(origin_features)*0.1+1))
                    print(f"top{bestk} best features is :{list(feat_import_dict.keys())[:bestk]}")
                    print(f"top{worstk} worst features is :{list(feat_import_dict.keys())[-worstk:]}")

                    #plot feature importance
                    plt.figure(figsize = (12, 2*bestk/5))
                    sns.barplot(
                        y=list(feat_import_dict.keys())[:bestk],
                        x=list(feat_import_dict.values())[:bestk],
                    )
                    plt.title(f"{model_name} fold {fold} top{bestk} best Feature Importance")
                    plt.show()
            
            if self.objective=='regression':
                if 'tabnet' not in model_name:
                    oof_preds[valid_index]=model.predict(X_valid)
                else:#tabnet
                    oof_preds[valid_index]=model.predict(X_valid.to_numpy()).reshape(-1)
            else:
                if 'tabnet' not in model_name:
                    oof_preds[valid_index]=model.predict_proba(X_valid)
                else:#tabnet
                    oof_preds[valid_index]=model.predict_proba(X_valid.to_numpy())
            if not use_optuna:#not find_params(training)
                if 'tabnet' not in model_name:
                    self.pickle_dump(model,self.model_save_path+f'{model_name}_fold{fold}.model')
                self.trained_models.append(copy.deepcopy(model))
            
            del X_train,y_train,X_valid,y_valid
            gc.collect()
        if self.exp_mode:#y and oof need expm1.
            #log(y+b)
            metric_score=self.Metric(np.expm1(y.values)-self.exp_mode_b,np.expm1(oof_preds)-self.exp_mode_b )
        else:
            metric_score=self.Metric(y.values,oof_preds)
        return oof_preds,metric_score
    
    def drop_high_correlation_feats(self,df:pd.DataFrame)->None:
        #target_col and group_col is for model training,don't delete.object feature is string.
        #Here we choose 0.99,other feature with high correlation can use Dimensionality reduction such as PCA.
        #if you want to delete other feature with high correlation,add into drop_cols when init.
        numerical_cols=[col for col in df.columns \
                        if (col not in [self.target_col,self.group_col]) \
                        and str(df[col].dtype) not in ['object','category']]
        corr_matrix=df[numerical_cols].corr().values
        drop_cols=[]
        for i in range(len(corr_matrix)):
            #time series data
            #bg0 and bg1 have correlation of 0.99,……,bg{n-1} and bg{n} have correlation of 0.99,
            #if don't add this,we will drop([bg1,……,bgn]),although bg0 and bgn have a low correlation.
            if numerical_cols[i] not in drop_cols:
                for j in range(i+1,len(corr_matrix)):
                    if numerical_cols[j]  not in drop_cols:
                        if abs(corr_matrix[i][j])>=0.99:
                            drop_cols.append(numerical_cols[j])
        #add drop_cols to self.drop_cols,they will be dropped in the final part of the function base_FE.
        print(f"drop_cols={drop_cols}")
        self.drop_cols+=drop_cols
    
    def fit(self,train_path_or_file:str|pd.DataFrame|pl.DataFrame='train.csv',
            sample_weight=1,category_cols:list[str]=[],
            target2idx:dict|None=None,
           ):
        if self.num_folds<2:#kfold must greater than 1
            raise ValueError("num_folds must be greater than 1.")
        #use your custom target2idx  when objective=='binary' or 'multi_class'
        self.use_custom_target2idx=(type(target2idx)==dict)
        #lightgbm:https://github.com/microsoft/LightGBM/blob/master/python-package/lightgbm/sklearn.py
        #xgboost:https://github.com/dmlc/xgboost/blob/master/python-package/xgboost/sklearn.py
        self.sample_weight=sample_weight
        #category_cols:Convert string columns to 'category'.
        self.category_cols=category_cols
        self.PrintColor("fit......",color=Fore.GREEN)
        self.PrintColor("load train data")
        self.load_data(path_or_file=train_path_or_file,mode='train')
        self.target_dtype=self.train[self.target_col].dtype
        try:#list_cols TypeError: unhashable type: 'list'
            self.train=self.train.drop_duplicates()
        except:
            pass
        print(f"train.shape:{self.train.shape}")
        self.PrintColor("Feature Engineer")
        self.train=self.base_FE(self.train,mode='train',drop_cols=self.drop_cols)
        
        #choose cross validation
        if self.objective!='regression':
            if self.group_col!=None:#group
                kf=StratifiedGroupKFold(n_splits=self.num_folds,random_state=self.seed,shuffle=True)
            else:
                kf=StratifiedKFold(n_splits=self.num_folds,random_state=self.seed,shuffle=True)
        else:#regression
            if self.group_col!=None:#group
                kf=GroupKFold(n_splits=self.num_folds)
            else:
                kf=KFold(n_splits=self.num_folds,random_state=self.seed,shuffle=True)
        
        X=self.train.drop([self.group_col,self.target_col],axis=1,errors='ignore')
        y=self.train[self.target_col]
        if self.exp_mode:#use log transform for target_col
            self.exp_mode_b=-y.min()
            y=np.log1p(y+self.exp_mode_b)
        if type(self.sample_weight)==int:#sample_weight=1,so no custom weights
            self.sample_weight=np.ones(len(y))
            
        if self.sample_weight.shape!=y.values.reshape(-1).shape:
            raise ValueError(f"shape of sample_weight must be {y.values.reshape(-1).shape}.")
        
        #special characters in columns'name will lead to errors when GBDT model training.
        self.col2name={}
        self.name2col={}
        X_columns=list(X.columns)
        for i in range(len(X_columns)):
            self.col2name[X_columns[i]]=f'col_{i}'
            self.name2col[f'col_{i}']=X_columns[i]
        X=X.rename(columns=self.col2name)
        self.categoryname=[self.col2name[col] for col in self.category_cols]
        print(f"feature_count:{len(X_columns)}")
        
        self.word2vec_colnames=[self.col2name[col] for col in self.word2vec_cols]
        self.labelencoder_colnames=[self.col2name[col] for col in self.labelencoder_cols]
                
        #classification:target2idx,idx2target
        if self.objective!='regression':
            if self.use_custom_target2idx:#use your custom target2idx
                self.target2idx=target2idx
                self.idx2target={}
                for tgt,idx in self.target2idx.items():
                    self.idx2target[idx]=tgt
            else:
                self.target2idx={}
                self.idx2target={}
                y_unique=list(y.value_counts().to_dict().keys())
                for idx in range(len(y_unique)):
                    self.target2idx[y_unique[idx]]=idx
                    self.idx2target[idx]=y_unique[idx]
            y=y.apply(lambda k:self.target2idx[k])
        
        if self.group_col!=None:
            group=self.train[self.group_col]
        else:
            group=None
        #save true label in train data to calculate final score  
        self.target=y.values

        kf_folds=pd.DataFrame({"fold":np.zeros(len(y))})
        for fold, (train_index, valid_index) in (enumerate(kf.split(X,y,group))):
            kf_folds['fold'][valid_index]=fold
        
        #if you don't use your own models,then use built-in models.
        self.PrintColor("load models")
        if len(self.models)==0:
            
            metric=self.metric
            if self.objective=='multi_class':
                metric='multi_logloss'
            #lightgbm don't support f1_score,but we will calculate f1_score as Metric.
            if metric in ['f1_score','mcc','logloss']:
                metric='auc'
            elif metric in ['medae','mape']:
                metric='mae'
            elif metric in ['rmsle','msle','r2']:
                metric='mse'
            if self.custom_metric!=None:
                if self.objective=='regression':
                    metric='rmse'
                elif self.objective=='binary':
                    metric='auc'
                elif self.objective=='multi_class':
                    metric='multi_logloss'
            if metric=='accuracy':
                metric='auc'
            lgb_params={"boosting_type": "gbdt","metric": metric,
                        'random_state': self.seed,  "max_depth": 10,"learning_rate": 0.1,
                        "n_estimators": 20000,"colsample_bytree": 0.6,"colsample_bynode": 0.6,"verbose": -1,"reg_alpha": 0.2,
                        "reg_lambda": 5,"extra_trees":True,'num_leaves':64,"max_bin":255,
                        }
            #find new params then use optuna
            if self.use_optuna_find_params:
                lgb_params=self.optuna_lgb(X=X,y=y,group=group,kf_folds=kf_folds,metric=metric)
             
            #catboost's metric
            # Valid options are:  'CrossEntropy', 'CtrFactor', 'Focal', 'RMSE', 'LogCosh', 
            # 'Lq','Quantile', 'MultiQuantile', 'Expectile', 'LogLinQuantile',
            # 'Poisson', 'MSLE', 'MedianAbsoluteError', 'SMAPE', 'Huber', 'Tweedie', 'Cox', 
            # 'RMSEWithUncertainty', 'MultiClass', 'MultiClassOneVsAll', 'PairLogit', 'PairLogitPairwise',
            # 'YetiRank', 'YetiRankPairwise', 'QueryRMSE', 'GroupQuantile', 'QuerySoftMax', 
            # 'QueryCrossEntropy', 'StochasticFilter', 'LambdaMart', 'StochasticRank', 
            # 'PythonUserDefinedPerObject', 'PythonUserDefinedMultiTarget', 'UserPerObjMetric',
            # 'UserQuerywiseMetric','NumErrors', 'FairLoss', 'BalancedAccuracy','Combination',
            # 'BalancedErrorRate', 'BrierScore', 'Precision', 'Recall', 'TotalF1', 'F', 'MCC', 
            # 'ZeroOneLoss', 'HammingLoss', 'HingeLoss', 'Kappa', 'WKappa', 'LogLikelihoodOfPrediction',
            # 'NormalizedGini', 'PRAUC', 'PairAccuracy', 'AverageGain', 'QueryAverage', 'QueryAUC',
            # 'PFound', 'PrecisionAt', 'RecallAt', 'MAP', 'NDCG', 'DCG', 'FilteredDCG', 'MRR', 'ERR', 
            # 'SurvivalAft', 'MultiRMSE', 'MultiRMSEWithMissingValues', 'MultiLogloss', 'MultiCrossEntropy',

            #catboost metric to params
            metric2params={#regression
                          'mse':'RMSE','rmsle':'RMSE','msle':'MSLE','rmse':'RMSE',
                           'mae':'MAE','medae':'MAE','mape':'MAPE','r2':'R2',
                          #classification
                           'accuracy':'Accuracy','logloss':'Logloss','multi_logloss':'Accuracy',
                           'f1_score':'F1','auc':'AUC','mcc':'MCC',
                          
                          }
            metric=metric2params.get(self.metric,'None')
            
            if self.custom_metric!=None:#use your custom_metric
                if self.objective=='regression':
                    metric='RMSE'
                elif self.objective=='binary':
                    metric='Logloss'
                else:
                    metric='Accuracy'
                    
            cat_params={
                       'random_state':self.seed,
                       'eval_metric'         : metric,
                       'bagging_temperature' : 0.50,
                       'iterations'          : 20000,
                       'learning_rate'       : 0.1,
                       'max_depth'           : 12,
                       'l2_leaf_reg'         : 1.25,
                       'min_data_in_leaf'    : 24,
                       'random_strength'     : 0.25, 
                       'verbose'             : 0,
                      }
            xgb_params={'random_state': self.seed, 'n_estimators': 20000, 
                        'learning_rate': 0.1, 'max_depth': 10,
                        'reg_alpha': 0.08, 'reg_lambda': 0.8, 
                        'subsample': 0.95, 'colsample_bytree': 0.6, 
                        'min_child_weight': 3,'early_stopping_rounds':self.early_stop,
                        'enable_categorical':True,
                       }

            if self.device in ['cuda','gpu']:#gpu's name
                lgb_params['device']='gpu'
                lgb_params['gpu_use_dp']=True
                cat_params['task_type']="GPU"
                xgb_params['tree_method']='gpu_hist'
                
            if self.objective=='regression':
                self.models=[(LGBMRegressor(**lgb_params),'lgb'),
                             (CatBoostRegressor(**cat_params),'cat'),
                             (XGBRegressor(**xgb_params),'xgb')
                            ]
            else:
                self.models=[(LGBMClassifier(**lgb_params),'lgb'),
                             (CatBoostClassifier(**cat_params),'cat'),
                             (XGBClassifier(**xgb_params),'xgb'),
                            ]
                
        for (model,model_name) in self.models:
            print(f"{model_name}_params={model.get_params()}")
        
        self.PrintColor("model training")
        for (model,model_name) in self.models:
            oof_preds,metric_score=self.cross_validation(X=X,y=y,group=group,kf_folds=kf_folds,model=model,model_name=model_name,sample_weight=self.sample_weight,use_optuna=False)
            self.PrintColor(f"{self.metric}------------------------------>{metric_score}",color = Fore.RED)
        
            if self.save_oof_preds:#if oof_preds is needed
                np.save(self.model_save_path+f"{model_name}_seed{self.seed}_fold{self.num_folds}.npy",oof_preds)

    def cal_final_score(self,weights):
        #calculate oof score if save_oof_preds
        if self.save_oof_preds:
            oof_preds=np.zeros_like(np.load(self.model_save_path+f"{self.models[0//self.num_folds][1]}_seed{self.seed}_fold{self.num_folds}.npy"))
            for i in range(0,len(weights),self.num_folds):
                oof_pred=np.load(self.model_save_path+f"{self.models[i//self.num_folds][1]}_seed{self.seed}_fold{self.num_folds}.npy")
                oof_preds+=weights[i]*oof_pred
            oof_preds=oof_preds/len(self.models)
            if self.exp_mode:
                print(f"final_{self.metric}:{self.Metric( np.expm1( self.target)-self.exp_mode_b,np.expm1( oof_preds)-self.exp_mode_b )}")
            else:
                print(f"final_{self.metric}:{self.Metric(self.target,oof_preds)}")

    def predict_batch(self,model,test_X):
        test_preds=np.zeros((len(test_X)))
        cat_cols=[col for col in test_X.columns if str(test_X[col].dtype) in ['category','object','string']]
        for idx in range(0,len(test_X),self.infer_size):
            try:
               test_preds[idx:idx+self.infer_size]=model.predict(test_X[idx:idx+self.infer_size])
            except:#NN such as tabnet 
               for c in cat_cols:
                   test_X[c]=test_X[c].apply(lambda x:int(x)).astype(np.int32)     
               test_preds[idx:idx+self.infer_size]=model.predict(test_X[idx:idx+self.infer_size].to_numpy()).reshape(-1)
        return test_preds

    def predict_proba_batch(self,model,test_X):
        test_preds=np.zeros((len(test_X),self.num_classes))
        cat_cols=[col for col in test_X.columns if str(test_X[col].dtype) in ['category','object','string']]
        for idx in range(0,len(test_X),self.infer_size):
            try:
                test_preds[idx:idx+self.infer_size]=model.predict_proba(test_X[idx:idx+self.infer_size])
            except:#NN such as tabnet
                for c in cat_cols:
                    test_X[c]=test_X[c].apply(lambda x:int(x)).astype(np.int32)     
                test_preds[idx:idx+self.infer_size]=model.predict_proba(test_X[idx:idx+self.infer_size].to_numpy())
        return test_preds
    
    def predict(self,test_path_or_file:str|pd.DataFrame|pl.DataFrame='test.csv',weights=None)->np.array:
        self.PrintColor("predict......",color=Fore.GREEN)
        #weights:[1]*len(self.models)
        n=len(self.models)
        #if you don't set weights,then calculate mean value as result.
        if weights==None:
            weights=np.ones(n)
        if len(weights)!=n:
            raise ValueError(f"length of weights must be {len(self.models)}.")
        self.PrintColor("weight normalization")
        weights=np.array([w for w in weights for f in range(self.num_folds)],dtype=np.float32)
        #normalization
        weights=weights*(self.num_folds*n)/np.sum(weights)

        #calculate oof score if save_oof_preds
        self.cal_final_score(weights)
        
        self.PrintColor("load test data")
        self.load_data(test_path_or_file,mode='test')
        print(f"test.shape:{self.test.shape}")
        
        self.PrintColor("Feature Engineer")
        self.test=self.base_FE(self.test,mode='test',drop_cols=self.drop_cols)
        self.test=self.test.drop([self.group_col,self.target_col],axis=1,errors='ignore')
        self.test=self.test.rename(columns=self.col2name)
        self.PrintColor("prediction on test data")
        if self.objective=='regression':
            test_preds=np.zeros((len(self.models)*self.num_folds,len(self.test)))
            cnt=0
            for idx in range(len(self.trained_models)): 
                test_copy=self.CV_FE(self.test.copy(),mode='test',fold=idx%self.num_folds)
                try:
                    test_pred=self.predict_batch(model=self.trained_models[idx],test_X=test_copy)
                except:#catboost
                    test_copy[self.categoryname]=test_copy[self.categoryname].astype('string')
                    test_pred=self.predict_batch(model=self.trained_models[idx],test_X=test_copy)
                test_preds[cnt]=test_pred
                cnt+=1
            test_preds=np.mean([test_preds[i]*weights[i] for i in range(len(test_preds))],axis=0)
            
            #use pseudo label
            if self.use_pseudo_label:
                self.test[self.target_col]=test_preds
                self.trained_models=[]
                self.fit(self.train_path_or_file,self.sample_weight,self.category_cols)
                #calculate oof score if save_oof_preds
                self.cal_final_score(weights)
                
                test_preds=np.zeros((len(self.models)*self.num_folds,len(self.test)))
                cnt=0
                for idx in range(len(self.trained_models)):
                    test_copy=self.CV_FE(self.test.copy(),mode='test',fold=idx%self.num_folds)
                    try:
                        test_pred=self.predict_batch(model=self.trained_models[idx],test_X=test_copy.drop([self.target_col],axis=1))
                    except:
                        test_copy[self.categoryname]=test_copy[self.categoryname].astype('string')
                        test_pred=self.predict_batch(model=self.trained_models[idx],test_X=test_copy.drop([self.target_col],axis=1))
                    test_preds[cnt]=test_pred
                    cnt+=1
                test_preds=np.mean([test_preds[i]*weights[i] for i in range(len(test_preds))],axis=0)
            if self.exp_mode:
                test_preds=np.expm1(test_preds)-self.exp_mode_b       
            return test_preds
        else:#classification 
            test_preds=np.zeros((len(self.models)*self.num_folds,len(self.test),self.num_classes))
            cnt=0
            for idx in range(len(self.trained_models)):
                test_copy=self.CV_FE(self.test.copy(),mode='test',fold=idx%self.num_folds)
                try:
                    test_pred=self.predict_proba_batch(model=self.trained_models[idx],test_X=test_copy)
                except:
                    test_copy[self.categoryname]=test_copy[self.categoryname].astype('string')
                    test_pred=self.predict_proba_batch(model=self.trained_models[idx],test_X=test_copy)
                test_preds[cnt]=test_pred
                cnt+=1   
            test_preds=np.mean([test_preds[i]*weights[i] for i in range(len(test_preds))],axis=0)#(len(test),self.num_classes)
            
            #use pseudo label
            if self.use_pseudo_label:
                self.test[self.target_col]=np.argmax(test_preds,axis=1)
                self.trained_models=[]
                self.fit(self.train_path_or_file,self.sample_weight,self.category_cols)
                #calculate oof score if save_oof_preds
                self.cal_final_score(weights)

                test_preds=np.zeros((len(self.models)*self.num_folds,len(self.test),self.num_classes))
                fold=0
                for idx in range(len(self.trained_models)):
                    test_copy=self.CV_FE(self.test.copy(),mode='test',fold=idx%self.num_folds)
                    try:
                        test_pred=self.predict_proba_batch(model=self.trained_models[idx],test_X=test_copy.drop([self.target_col],axis=1))
                    except:
                        test_copy[self.categoryname]=test_copy[self.categoryname].astype('string')
                        test_pred=self.predict_proba_batch(model=self.trained_models[idx],test_X=test_copy.drop([self.target_col],axis=1))
                    test_preds[fold]=test_pred
                    fold+=1
                test_preds=np.mean([test_preds[i]*weights[i] for i in range(len(test_preds))],axis=0)
            if self.metric=='auc':
                return test_preds[:,1]
            if self.save_test_preds:
                self.PrintColor(f"idx2target={self.idx2target}",color=Fore.RED)
                self.pickle_dump(self.idx2target,self.model_save_path+'idx2target.pkl')
                np.save(self.model_save_path+'test_preds.npy',test_preds)
            test_preds=np.argmax(test_preds,axis=1)
            return test_preds

    def predict_proba(self,test_path_or_file:str|pd.DataFrame|pl.DataFrame='test.csv',weights=None)->np.array:
        self.save_test_preds=True
        test_preds=self.predict(test_path_or_file,weights)
        test_proba=np.load(self.model_save_path+'test_preds.npy')
        return test_proba
        
    #ensemble some solutions.
    def ensemble(self,solution_paths_or_files:list[str]=[],weights=None):
        #If you don't set weights,then use mean value as result.
        n=len(solution_paths_or_files)
        if weights==None:
            weights=np.ones(n)
        if len(weights)!=n:
            raise ValueError(f"length of weights must be len(solution_paths_or_files).")
        #normalization
        weights=weights/np.sum(weights)

        #Weighted Sum of Continuous Values
        if (self.objective=='regression') or(self.metric=='auc'):
            final_solutions=[]
            for i in range(n):
                if type(solution_paths_or_files[i])==str:#csv file path
                    try:
                        solution=pl.read_csv(solution_paths_or_files[i])
                        solution=solution.to_pandas()
                    except:
                        raise ValueError("Yunbase can only support csv file.")
                else:#csv_file have load
                    solution=solution_paths_or_files[i].copy()
                if not isinstance(solution, pd.DataFrame):
                    raise ValueError("solution_paths_or_files is not pd.DataFrame.")
                final_solutions.append(weights[i]*solution[self.target_col].values)
            final_solutions=np.sum(final_solutions,axis=0)
            return final_solutions
        else:#classification find mode
            #n solutions,m datas
            solutions=[]
            for i in range(n):
                if type(solution_paths_or_files[i])==str:
                    try:
                        solution=pl.read_csv(solution_paths_or_files[i])
                        solution=solution.to_pandas()
                    except:
                        raise ValueError("Yunbase can only support csv file.")
                else:#csv_file have load
                    solution=solution_paths_or_files[i].copy()
                if not isinstance(solution, pd.DataFrame):
                    raise ValueError("solution_paths_or_files is not pd.DataFrame.")
                solutions.append(solution[self.target_col].values)
            final_solutions=[]
            for i in range(len(solutions[0])):
                solution2count={}
                #data[i] solution[j]
                for j in range(n):
                    if solutions[j][i] in solution2count.keys():
                        solution2count[ solutions[j][i] ]+=weights[j]
                    else:
                        solution2count[ solutions[j][i] ]=weights[j]
                solution2count=dict(sorted(solution2count.items(),key=lambda x:-x[1]))
                final_solutions.append(list(solution2count.keys())[0])
            final_solutions=np.array(final_solutions)
            return final_solutions

    #save test_preds to submission.csv
    def submit(self,submission_path_or_file:str|pd.DataFrame='submission.csv',test_preds:np.array=np.ones(3),save_name:str='yunbase'):
        self.PrintColor('submission......',color = Fore.GREEN)
        submission=self.load_data(submission_path_or_file,mode='submission')
        submission[self.target_col]=test_preds
        if self.objective!='regression':
            if self.metric!='auc':
                submission[self.target_col]=submission[self.target_col].apply(lambda x:self.idx2target[x])
        #target is True and False
        if self.target_dtype==bool:
            submission[self.target_col]=submission[self.target_col].astype(bool)
        submission.to_csv(f"{save_name}.csv",index=None)