from gensim.models import KeyedVectors
import numpy as np
import pandas as pd
import argparse
import os
import joblib
import json
import time
import logging


LOG_FOLDER = "pipeline_logs/"

parser = argparse.ArgumentParser(description='Postprocessing of trained models')
parser.add_argument('--lang', type=str, help='list CSV files', required=True)
parser.add_argument('--dataset_name', type=str, help='list CSV files', required=True)
parser.add_argument('--csvs', nargs='+', help='list CSV files', required=True)
parser.add_argument('--embeddings', type=str, help='embeddings path', required=True)
parser.add_argument('--lemma_word_mapping', type=str, help='lemma_word_mapping path', required=True)
args = parser.parse_args()

LOG_FILE = os.path.join(LOG_FOLDER, f'{args.lang}_postprocess_{args.dataset_name}.txt')
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE,
    filemode='a',
    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
    datefmt='%H:%M:%S',
    level=logging.INFO
)

start = time.time()

logging.info(f'Loading embeddings at {args.embeddings}...')
embeddings = KeyedVectors.load(args.embeddings, mmap='r')
logging.info(f'Loaded embeddings')

logging.info(f'Loading lemma word mapping...')
lemma_word_mapping = json.load(open(args.lemma_word_mapping))["lemma_word"]
logging.info(f'Lemma word mapping loaded')


def get_topics_vectors(topics, lemma_word_mapping, embeddings_file):
    topics_words = [list(map(lambda x: x[1], topic)) for topic in topics]

    word_vectors = [[] for topic in topics]
    word_weights = [[] for topic in topics]

    for idx, topic in enumerate(topics_words):
        for i in range(len(topic)):
            word = topic[i]
            try:
                vector = embeddings[word]
                word_prob_pair = topics[idx][i]
                (prob, _) = word_prob_pair
                word_vectors[idx].append((i, vector))
                word_weights[idx].append((i, prob))
            except:
              for original_word in lemma_word_mapping[word]:
                try:
                    vector = embeddings[original_word]
                    word_prob_pair = topics[idx][i]
                    (prob, _) = word_prob_pair
                    word_vectors[idx].append((i, vector))
                    word_weights[idx].append((i, prob))
                    break
                except: 
                    continue
    
    flattened_word_vectors = []
    for topic in word_vectors:
        topic.sort(key=idx_sort)
        flattened_word_vectors.append(list(map(lambda x: x[1], topic)))
    
    flattened_word_weights = []
    for topic in word_weights:
        topic.sort(key=idx_sort)
        flattened_word_weights.append(list(map(lambda x: x[1], topic)))
    
    return flattened_word_vectors, flattened_word_weights


def get_average_topics_vectors(word_vectors, word_weights):
    weighted_topics = []
    for idx, topic in enumerate(word_vectors):
        weighted_topics.append([np.multiply(topic[i], word_weights[idx][i]) for i in range(len(topic))])

    return [np.mean(word_vectors, axis=0) for word_vectors in weighted_topics]


def idx_sort(element):
    return element[0]


def get_most_similar_terms_to_topic(topic_vector, top_n = 10):
    return embeddings.most_similar(positive=[topic_vector], topn=top_n)

logging.info(f'Starting postprocessing...')
for csv in args.csvs:
    logging.info(f'Postprocessing models found in CSV: {csv}...')
    training_results = pd.read_csv(csv)
    models_paths = training_results['path'].tolist()
    models_base_path = os.path.sep.join(csv.split(os.path.sep)[:-2])

    for model_path in models_paths:
        path_to_load = os.path.join(models_base_path, "models", model_path)
        logging.info(f'Loading model at: {path_to_load}')
        model = joblib.load(path_to_load)
        word_vectors, word_weights = get_topics_vectors(
            model["topics_with_word_probs"], 
            lemma_word_mapping, 
            args.embeddings,
        )
        model["topics_vectors"] = {
            "word_vectors": word_vectors, 
            "word_weights": word_weights
        }
        del word_vectors
        del word_weights
        model["averaged_topics_vectors"] = get_average_topics_vectors(model["topics_vectors"]["word_vectors"], model["topics_vectors"]["word_weights"])
        model["most_similar_words"] = [get_most_similar_terms_to_topic(topic) for topic in model["averaged_topics_vectors"]]
        joblib.dump(model, path_to_load, compress=8)
        del model
        logging.info(f'Saved model at {path_to_load}')
        del path_to_load

    del training_results
    del models_paths
    del models_base_path
    logging.info(f'Postprocessing finished for models found in CSV: {csv}')
    del csv

del embeddings
del lemma_word_mapping

end = time.time()

logging.info(f'Postprocessing finished - Elapsed execution time: {end-start}s')
