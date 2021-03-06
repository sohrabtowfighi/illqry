docs_string = """
   
    illqry - Tool for checking symptom-disease and disease-disease links
    Provided as is with no warranty whatsoever,
    not even for intended purpose.
    Sohrab Towfighi, MD Candidate at Univ. Toronto
    GNU GPL V2 Licence. (c) 2017
    Uses data from doi:10.1038/ncomms5212
  

   python3 illqry.py $path_to_illqry_db [$option] $arg1 [$arg2] ... [$argN]

   [options]
   -h       print the documentation string
   -s       setup the illqry database file. You must create an empty file with 
            a .db extension, this script will not create the empty file for you.
   -d       run with disease mode - $arg1 ... $argN are various diseases,
            the resulting report will provide list of common symptoms
   -ld      list all the diseases, you can supply an additional argument, which 
            will modify functionality to return only diseases containing the 
            string supplied in the additional argument
   -ls      list all the symptoms, you can supply an additional argument, which 
            will modify functionality to return only symptoms containing the 
            string supplied in the additional argument

   SETUP of DATABASE FILE
   illqry_db.db file is a sqlite3 file created using this same script. 
   Setup the illqry_db.db file using "python3 illqry.py -s" 

   STANDARD USEAGE
   python3 illqry.py $path_to_illqry_db Cough Hemoptysis

   DISEASE BASED USEAGE
   python3 illqry.py $path_to_illqry_db -d "Wolff-Parkinson-White Syndrome"

   Pass along arguments which are the relevant symptoms.
   Enter MeSH symptoms in quotes so that they are captured as distinct.
"""

file_not_already_created_error_string = '''The database file needs to pre-exist. 
        If you are setting up the database file for the first time. 
        You need to create an empty .db file before running this script.'''

from numpy import product
import numpy as np
import pdb
import sqlite3
import sys
import csv
import tabulate
from string import ascii_uppercase
import os 

class Disease(object):
    def __init__(self, name, symptom, score):
        self._name = name
        self._symptom = symptom
        self._score = score

def make_dbs():
    cur = conn.cursor()
    cur.execute("""DROP TABLE IF EXISTS symptoms_diseases""")
    cur.execute("""DROP TABLE IF EXISTS diseases_diseases""")
    cur.execute("""CREATE TABLE symptoms_diseases (
                    symptom  TEXT,
                    disease  TEXT,
                    occurs   INT,
                    score    FLOAT)""")
            
    cur.execute("""CREATE TABLE diseases_diseases (
                    disease_1 INT,
                    disease_2 INT,
                    score     TEXT)""")
                    
    all_symptoms = list()
    all_diseases = list()
    with open('ncomms5212-s4.txt') as mycsv:
        rdr = csv.reader(mycsv, delimiter='\t')
        rdr.__next__()
        for line in rdr: 
            print('Working on symptoms-disease' + str(line))
            cur.execute("""INSERT INTO symptoms_diseases VALUES (?, ?, ?, ?)""", 
                        (line[0], line[1], line[2], line[3]))
            all_symptoms.append((line[0],))
            all_diseases.append((line[1],))
        conn.commit()
    with open('symptoms.txt', 'w') as symps:
        wrtr = csv.writer(symps, lineterminator='\n', delimiter=';')
        all_symptoms = list(set(all_symptoms))
        for symptom in sorted(all_symptoms):
            wrtr.writerow(symptom)
    with open('diseases.txt', 'w') as dses:
        wrtr = csv.writer(dses, lineterminator='\n', delimiter=';')
        all_diseases = list(set(all_diseases))
        for disease in sorted(all_diseases):
            wrtr.writerow(disease)
    with open('ncomms5212-s5.txt') as mycsv:       
        rdr = csv.reader(mycsv, delimiter='\t')
        rdr.__next__()
        for line in rdr:  
            print('Working on disease-disease' + str(line))
            cur.execute("""INSERT INTO diseases_diseases VALUES (?, ?, ?)""", 
                        (line[0], line[1], line[2]))
        conn.commit()

def get_relevant_diseases_one_symptom(symptom, conn):    
    diseases_one_symptom = list()
    cur = conn.cursor()
    cur.execute("""SELECT disease,score FROM symptoms_diseases 
                   WHERE symptom = ?""", (symptom,))
    for row in cur:
        diseases_one_symptom.append((row[0], row[1]))
    return diseases_one_symptom
        
def get_relevant_diseases(symptoms, db_path):
    conn = sqlite3.connect(db_path)
    diseases = []
    separated_diseases = []
    for symptom in symptoms:
        subset_diseases = get_relevant_diseases_one_symptom(symptom, conn)
        diseases = diseases + subset_diseases       
        separated_diseases.append(subset_diseases)
        if len(subset_diseases) == 0:
            raise Exception("For symptom: " + symptom + '\nNo diseases found.'+
                            'Check MeSH term.')
    return diseases, separated_diseases

def get_joint_relevant_diseases(symptoms, db_path):
    conn = sqlite3.connect(db_path)
    diseases_all_symptoms = list()
    cur = conn.cursor()
    qry_string = """SELECT * FROM 
                    (SELECT * FROM symptoms_diseases                     
                    WHERE symptom = ?) AS A """ 
    for i in range(1,len(symptoms)):    
        Letter = str(ascii_uppercase[i])
        qry_string += " INNER JOIN (SELECT * FROM symptoms_diseases WHERE symptom = ?) AS " + Letter
        qry_string += " ON A.disease = " + Letter + '.disease '
    cur.execute(qry_string, symptoms)
    for row in cur:
        diseases_all_symptoms.append((row))
    scores = np.zeros((len(diseases_all_symptoms), len(symptoms)+1))
    
    for i in range(0,len(diseases_all_symptoms)):
        old_row = diseases_all_symptoms[i]
        new_row = list()
        new_row.append(old_row[1])
        for j in range(0,len(symptoms)):
            new_row.append(old_row[3+4*j])
        scores[i,1:] = new_row[1:]
    for j in range(1,1+len(symptoms)):
        scores[:,j] = scores[:,j]/np.sum(scores[:,j])
        if j == 2:
            scores[:,0] = np.multiply(scores[:,1], scores[:,2])
        elif j > 2:
            scores[:,0] = np.multiply(scores[:,0],scores[:,j])
    scores = scores.tolist()
    refined_diseases_all_symptoms = list()
    for i in range(0,len(diseases_all_symptoms)):
        refined_diseases_all_symptoms.append([diseases_all_symptoms[i][1]] +
                                             scores[i])
    return refined_diseases_all_symptoms
    
def sort_diseases(symptoms, separated_diseases, db_path):
    output_file = 'report.txt'
    report_string = ''
    with open(output_file, 'w+') as my_report:
        if len(symptoms) > 1:
            joint_disease_set = get_joint_relevant_diseases(symptoms, db_path)
            sorted_joint_disease_set = sorted(joint_disease_set, 
                                              key=lambda x:x[1], 
                                              reverse=True)
            tbl0 = tabulate.tabulate(sorted_joint_disease_set)
            report_string += '\n'+' AND '.join(symptoms)+'\n'+tbl0
        my_report.write(report_string)
        for i in range(0,len(symptoms)):
            disease_set = separated_diseases[i]
            symptom = symptoms[i]
            sorted_disease_set = sorted(disease_set, key=lambda x:x[1], 
                                        reverse=True)
            tbl = tabulate.tabulate(sorted_disease_set)
            report_string += '\n'+symptom+'\n'+tbl
        my_report.write(report_string)
    return report_string

def get_symptoms_of_disease(disease, db_path):
    conn = sqlite3.connect(db_path)
    symptoms_one_disease = list()
    cur = conn.cursor()
    cur.execute("""SELECT symptom,score FROM symptoms_diseases 
                   WHERE disease = ?""", (disease,))
    for row in cur:
        symptoms_one_disease.append((row[0], row[1]))
    return symptoms_one_disease

def sort_symptoms(symptoms, disease):
    output_file = 'report.txt'
    report_string = ''
    with open(output_file, 'w+') as my_report:
        sorted_symptoms = sorted(symptoms, key=lambda x:x[1], reverse=True)
        tbl = tabulate.tabulate(sorted_symptoms)
        report_string = '\n'+disease+'\n'+tbl
        my_report.write(report_string)
    print(report_string)

        
def read_from_db(db_path, txtcontains='', symptom_or_disease='symptom'):
    conn = sqlite3.connect(db_path)
    diseases_or_symptoms = list()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT " + symptom_or_disease + " FROM symptoms_diseases")
    for row in cur:
        disease_or_symptom = row[0]
        if len(txtcontains) > 0:

            if (txtcontains.lower() in disease_or_symptom.lower()) == True: 
            # only grab diseases which start with the specified text 
            # if no text specified, grabs all the diseases 
                diseases_or_symptoms.append(disease_or_symptom)
            else:
                pass 
        else:
            diseases_or_symptoms.append(disease_or_symptom)
    return sorted(diseases_or_symptoms)
        
def read_diseases(db_path, txtcontains=''):
    return read_from_db(db_path, txtcontains, symptom_or_disease='disease')

def read_symptoms(db_path, txtcontains=''):
    return read_from_db(db_path, txtcontains, symptom_or_disease='symptom')

if __name__ == '__main__':
    args = sys.argv[1:]
    path_to_db = os.path.join(args[0])
    if os.path.isfile(path_to_db) == False:
        print(file_not_already_created_error_string)
        exit(0) 
    if len(args) == 0:
        print(docs_string)
        exit(0)
    elif len(args) == 1 and args[0] == '-s':
        make_dbs()
    elif args[1] == '-ld':
        text=''
        if len(args) == 3:
            text = args[2]
        diseases = read_diseases(path_to_db, txtcontains=text)
        diseases = sorted(diseases)
        for line in diseases:
            print(line)
    elif args[1] == '-ls':
        text=''
        if len(args) == 3:
            text = args[2]
        symptoms = read_symptoms(path_to_db, txtcontains=text)
        symptoms = sorted(symptoms)
        for line in symptoms:
            print(line)
    elif args[1] == '-d':
        # disease mode
        disease = args[2]
        symptoms = get_symptoms_of_disease(disease, path_to_db)
        symptoms_report = sort_symptoms(symptoms, disease)        
        print(symptoms_report)
    else:
        # the arguments should be taken as MeSH symptom terms
        symptoms = args[1:]
        my_diseases, separated_diseases = get_relevant_diseases(symptoms, path_to_db)
        diseases_report = sort_diseases(symptoms, separated_diseases, path_to_db)
        print(diseases_report)
