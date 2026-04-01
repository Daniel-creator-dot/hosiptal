"""
Outstanding Drug Classification Guide for Doctors and Pharmacy Staff
Comprehensive hierarchical drug reference with detailed subcategories
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count, Sum, F
from django.http import JsonResponse
from hospital.models import Drug, PharmacyStock


@login_required
def drug_classification_guide(request):
    """
    Outstanding comprehensive drug classification guide
    Hierarchical dropdown navigation for doctors and pharmacy
    """
    # Get encounter_id from query parameter if present (for prescription linking)
    encounter_id = request.GET.get('encounter_id', None)
    
    # Build comprehensive drug classification structure
    drug_classification = {
        'PAIN_MANAGEMENT': {
            'name': 'Pain Management & Fever',
            'icon': '💊',
            'categories': {
                'Analgesics': {
                    'description': 'Drugs that relieve pain. There are two main types: non-narcotic analgesics for mild pain, and narcotic analgesics for severe pain.',
                    'examples': ['Paracetamol', 'Aspirin', 'Ibuprofen', 'Morphine', 'Codeine', 'Tramadol']
                },
                'Antipyretics': {
                    'description': 'Drugs that reduce fever',
                    'examples': ['Paracetamol', 'Aspirin', 'Ibuprofen']
                },
                'Anti-Inflammatories': {
                    'description': 'Drugs used to reduce inflammation - the redness, heat, swelling, and increased blood flow found in infections and in many chronic noninfective diseases such as rheumatoid arthritis and gout.',
                    'examples': ['Ibuprofen', 'Naproxen', 'Diclofenac', 'Indomethacin', 'Celecoxib']
                }
            }
        },
        'CARDIOVASCULAR': {
            'name': 'Cardiovascular System',
            'icon': '❤️',
            'categories': {
                'Antihypertensives': {
                    'description': 'Drugs that lower blood pressure. The types of antihypertensives currently marketed include diuretics, beta-blockers, calcium channel blocker, ACE (angiotensin-converting enzyme) inhibitors, centrally acting antihypertensives and sympatholytics.',
                    'subcategories': {
                        'Diuretics': {
                            'subsubcategories': {
                                'Thiazides': ['Hydrochlorothiazide', 'Chlorthalidone', 'Indapamide'],
                                'High Ceiling': ['Furosemide', 'Bumetanide'],
                                'Potassium-Sparing': ['Spironolactone', 'Eplerenone', 'Amiloride']
                            }
                        },
                        'Renin-Angiotensin System Inhibitors': {
                            'subsubcategories': {
                                'ACE Inhibitors': ['Captopril', 'Enalapril', 'Lisinopril', 'Perindopril', 'Ramipril', 'Fosinopril'],
                                'Angiotensin AT₁ Receptor Blockers': ['Losartan', 'Candesartan', 'Valsartan', 'Telmisartan', 'Irbesartan'],
                                'Direct Renin Inhibitor': ['Aliskiren']
                            }
                        },
                        'Calcium Channel Blockers': {
                            'subsubcategories': {
                                'Phenylalkylamine': ['Verapamil'],
                                'Benzothiazepine': ['Diltiazem'],
                                'Dihydropyridine': ['Nifedipine', 'Felodipine', 'Amlodipine', 'Nitrendipine']
                            }
                        },
                        'Vasodilators': {
                            'subsubcategories': {
                                'Arteriolar Dilator': ['Hydralazine', 'Minoxidil'],
                                'Arteriolar + Venodilator': ['Sodium Nitroprusside']
                            }
                        },
                        'Sympathetic Inhibitors': {
                            'subsubcategories': {
                                'Beta Adrenergic Blockers': ['Propranolol', 'Metoprolol', 'Atenolol'],
                                'Alpha+Beta Blockers': ['Labetalol', 'Carvedilol'],
                                'Alpha-Adrenergic Blockers': ['Prazosin', 'Terazosin', 'Doxazosin'],
                                'Central Sympatholytics': ['Clonidine', 'Methyldopa']
                            }
                        }
                    }
                },
                'Antianginal Drugs': {
                    'description': 'Treat angina',
                    'subcategories': {
                        'Nitrates': {
                            'subsubcategories': {
                                'Short Acting': ['Glyceryl Trinitrate', 'Isosorbide Dinitrate (sublingual)'],
                                'Long Acting': ['Isosorbide Dinitrate (oral)', 'Isosorbide Mononitrate']
                            }
                        },
                        'Beta Blockers': ['Propranolol', 'Metoprolol', 'Atenolol'],
                        'Calcium Channel Blockers': ['Verapamil', 'Diltiazem', 'Amlodipine'],
                        'Post Channel Opener': ['Nicorandil'],
                        'Other': ['Trimetazidine', 'Ranolazine', 'Ivabradine']
                    }
                },
                'Antiarrhythmics': {
                    'description': 'Control irregularities of heartbeat',
                    'subcategories': {
                        'Class I: Membrane Stabilizing': {
                            'subsubcategories': {
                                'Moderately Decrease (Class IA)': ['Quinidine', 'Procainamide', 'Disopyramide'],
                                'Little Decrease (Class IB)': ['Lidocaine', 'Mexiletine'],
                                'Marked Decrease (Class IC)': ['Propafenone', 'Flecainide']
                            }
                        },
                        'Class II: Antiadrenergic': ['Propranolol', 'Sotalol', 'Esmolol'],
                        'Class III: Widen Action Potential': ['Amiodarone', 'Dronedarone', 'Dofetilide'],
                        'Class IV: Calcium Channel Blockers': ['Verapamil', 'Diltiazem'],
                        'PSVT Drugs': ['Adenosine', 'Digoxin']
                    }
                },
                'Anticoagulants': {
                    'description': 'Prevent blood from clotting',
                    'subcategories': {
                        'Parenteral': {
                            'subsubcategories': {
                                'Indirect Thrombin Inhibitors': {
                                    'Heparins': ['Heparin (unfractionated)', 'Enoxaparin', 'Dalteparin', 'Nadroparin'],
                                    'Others': ['Fondaparinux', 'Danaparoid']
                                },
                                'Direct Thrombin Inhibitors': ['Lepirudin', 'Bivalirudin', 'Argatroban']
                            }
                        },
                        'Oral': {
                            'subsubcategories': {
                                'Coumarin Derivatives': ['Warfarin', 'Acenocoumarol', 'Dicumarol'],
                                'Direct Factor Xa Inhibitor': ['Rivaroxaban'],
                                'Oral Direct Thrombin Inhibitor': ['Dabigatran']
                            }
                        }
                    }
                },
                'Antiplatelet Drugs': {
                    'description': 'Prevent platelet aggregation',
                    'subcategories': {
                        'Thromboxane Synthesis Inhibitor': ['Aspirin'],
                        'Platelet cAMP Enhancer': ['Dipyridamole'],
                        'P2Y12 Receptor Blockers': ['Ticlopidine', 'Clopidogrel', 'Prasugrel'],
                        'GP IIb/IIIa Antagonists': ['Abciximab', 'Eptifibatide', 'Tirofiban']
                    }
                },
                'Thrombolytics (Fibrinolytics)': {
                    'description': 'Dissolve blood clots',
                    'examples': ['Streptokinase', 'Urokinase', 'Alteplase (rt-PA)', 'Reteplase', 'Tenecteplase']
                },
                'Drugs for CHF': {
                    'description': 'Congestive Heart Failure',
                    'subcategories': {
                        'Inotropic Drugs': {
                            'subsubcategories': {
                                'Cardiac Glycosides': ['Digoxin', 'Ouabain'],
                                'Sympathomimetics': ['Dobutamine', 'Dopamine'],
                                'PDE 3 Inhibitors': ['Inamrinone', 'Milrinone']
                            }
                        },
                        'Diuretics': ['Furosemide', 'Bumetanide'],
                        'ACE Inhibitors': ['Enalapril', 'Ramipril'],
                        'ARBs': ['Losartan', 'Candesartan'],
                        'Beta Blockers': ['Metoprolol', 'Bisoprolol', 'Carvedilol'],
                        'Aldosterone Antagonists': ['Spironolactone', 'Eplerenone']
                    }
                },
                'Hypolipidaemic Drugs': {
                    'description': 'Lower lipid levels',
                    'subcategories': {
                        'HMG-CoA Reductase Inhibitors (Statins)': ['Lovastatin', 'Simvastatin', 'Atorvastatin', 'Rosuvastatin'],
                        'Fibrates': ['Clofibrate', 'Gemfibrozil', 'Fenofibrate'],
                        'Bile Acid Sequestrants': ['Cholestyramine', 'Colestipol'],
                        'Sterol Absorption Inhibitor': ['Ezetimibe'],
                        'Nicotinic Acid': ['Nicotinic Acid']
                    }
                },
                'Haematinics': {
                    'description': 'Treat anemia',
                    'subcategories': {
                        'Iron Preparations': {
                            'subsubcategories': {
                                'Oral Iron': ['Ferrous Sulfate', 'Ferrous Fumarate', 'Ferrous Gluconate'],
                                'Parenteral Iron': ['Iron Dextran', 'Ferrous Sucrose', 'Ferric Carboxy Maltose']
                            }
                        },
                        'Maturation Factors': {
                            'subsubcategories': {
                                'Vitamin B12': ['Cyanocobalamin', 'Methylcobalamin'],
                                'Folic Acid': ['Folic Acid', 'Folinic Acid']
                            }
                        }
                    }
                },
                'Coagulants': {
                    'description': 'Promote blood clotting',
                    'subcategories': {
                        'Vitamin K': ['Phytonadione (K1)', 'Menadione (K3)'],
                        'Miscellaneous': ['Fibrinogen', 'Desmopressin', 'Ethamsylate']
                    }
                }
            }
        },
        'INFECTIONS': {
            'name': 'Infections & Antimicrobials',
            'icon': '🦠',
            'categories': {
                'Antibiotics': {
                    'description': 'Combat bacterial infections',
                    'subcategories': {
                        'Penicillins': {
                            'subsubcategories': {
                                'Natural Penicillin': ['Benzyl Penicillin (Penicillin G)'],
                                'Semisynthetic': {
                                    'Acid Resistant': ['Phenoxymethyl Penicillin (Penicillin V)'],
                                    'Penicillinase Resistant': ['Methicillin', 'Cloxacillin', 'Dicloxacillin'],
                                    'Extended Spectrum': {
                                        'Amino-penicillins': ['Ampicillin', 'Amoxicillin'],
                                        'Carboxy-penicillins': ['Carbenicillin'],
                                        'Ureido-penicillins': ['Piperacillin']
                                    }
                                },
                                'Beta-Lactamase Inhibitors': ['Clavulanic Acid', 'Sulbactam', 'Tazobactam']
                            }
                        },
                        'Cephalosporins': {
                            'subsubcategories': {
                                '1st Generation': {
                                    'Oral': ['Cephalexin', 'Cefadroxil'],
                                    'Parenteral': ['Cefazolin']
                                },
                                '2nd Generation': {
                                    'Oral': ['Cefaclor', 'Cefuroxime Axetil'],
                                    'Parenteral': ['Cefuroxime', 'Cefoxitin']
                                },
                                '3rd Generation': {
                                    'Oral': ['Cefixime', 'Cefpodoxime', 'Cefdinir'],
                                    'Parenteral': ['Cefotaxime', 'Ceftriaxone', 'Ceftazidime', 'Cefoperazone']
                                },
                                '4th Generation': {
                                    'Parenteral': ['Cefepime', 'Cefpirome']
                                }
                            }
                        },
                        'Sulfonamides': {
                            'subsubcategories': {
                                'Short Acting': ['Sulfadiazine'],
                                'Intermediate Acting': ['Sulfamethoxazole'],
                                'Long Acting': ['Sulfadoxine'],
                                'Special Purpose': ['Sulfacetamide', 'Sulfasalazine', 'Silver Sulfadiazine']
                            }
                        },
                        'Quinolones': {
                            'subsubcategories': {
                                'Nonfluorinated': ['Nalidixic Acid'],
                                'Fluoroquinolones': {
                                    '1st Generation': ['Norfloxacin', 'Ciprofloxacin', 'Ofloxacin'],
                                    'Special Purpose': ['Levofloxacin', 'Moxifloxacin', 'Gemifloxacin']
                                }
                            }
                        },
                        'Antitubercular Drugs': {
                            'subsubcategories': {
                                '1st Line': ['Isoniazid', 'Rifampin', 'Pyrazinamide', 'Ethambutol'],
                                '2nd Line Injectable': ['Streptomycin', 'Kanamycin', 'Amikacin'],
                                '2nd Line Fluoroquinolones': ['Ofloxacin', 'Levofloxacin', 'Moxifloxacin'],
                                '2nd Line Oral': ['Ethionamide', 'Cycloserine', 'Para-aminosalicylic Acid']
                            }
                        },
                        'Antileprotic Drugs': {
                            'examples': ['Dapsone', 'Clofazimine', 'Rifampin']
                        },
                        'Aminoglycosides': {
                            'subsubcategories': {
                                'Systemic': ['Gentamicin', 'Tobramycin', 'Amikacin', 'Streptomycin', 'Kanamycin'],
                                'Topical': ['Neomycin', 'Framycetin']
                            }
                        },
                        'Macrolides': {
                            'subsubcategories': {
                                '1st Generation': ['Erythromycin'],
                                '2nd Generation': ['Clarithromycin', 'Azithromycin', 'Roxithromycin'],
                                'Ketolides': ['Telithromycin']
                            }
                        },
                        'Tetracyclines': {
                            'subsubcategories': {
                                'Short Acting': ['Tetracycline', 'Oxytetracycline'],
                                'Intermediate Acting': ['Demeclocycline'],
                                'Long Acting': ['Doxycycline', 'Minocycline']
                            }
                        },
                        'Glycopeptides': {
                            'examples': ['Vancomycin', 'Teicoplanin']
                        },
                        'Carbapenems': {
                            'examples': ['Imipenem', 'Meropenem', 'Ertapenem', 'Doripenem']
                        },
                        'Monobactams': {
                            'examples': ['Aztreonam']
                        },
                        'Lincosamides': {
                            'examples': ['Clindamycin', 'Lincomycin']
                        },
                        'Oxazolidinones': {
                            'examples': ['Linezolid', 'Tedizolid']
                        },
                        'Polymyxins': {
                            'examples': ['Polymyxin B', 'Colistin']
                        },
                        'Chloramphenicol': {
                            'examples': ['Chloramphenicol']
                        }
                    }
                },
                'Antivirals': {
                    'description': 'Treat viral infections',
                    'subcategories': {
                        'Anti-Herpes': ['Acyclovir', 'Valacyclovir', 'Famciclovir', 'Ganciclovir'],
                        'Anti-Influenza': ['Oseltamivir', 'Zanamivir', 'Amantadine'],
                        'Anti-Hepatitis B': ['Lamivudine', 'Adefovir', 'Tenofovir'],
                        'Anti-Hepatitis C': ['Ribavirin', 'Interferon Alpha'],
                        'Antiretroviral (HIV)': {
                            'subsubcategories': {
                                'NRTIs': ['Zidovudine', 'Lamivudine', 'Tenofovir'],
                                'NNRTIs': ['Nevirapine', 'Efavirenz'],
                                'Protease Inhibitors': ['Ritonavir', 'Atazanavir'],
                                'Integrase Inhibitors': ['Raltegravir']
                            }
                        }
                    }
                },
                'Antifungals': {
                    'description': 'Treat fungal infections',
                    'examples': ['Fluconazole', 'Itraconazole', 'Ketoconazole', 'Amphotericin B']
                },
                'Antimalarials': {
                    'description': 'Treat malaria',
                    'subcategories': {
                        '4-Aminoquinolines': ['Chloroquine', 'Amodiaquine'],
                        '8-Aminoquinolines': ['Primaquine'],
                        'Artemisinin Derivatives': ['Artesunate', 'Artemether'],
                        'Antifolates': ['Sulfadoxine-Pyrimethamine'],
                        'Others': ['Quinine', 'Mefloquine', 'Doxycycline']
                    }
                },
                'Anthelmintics': {
                    'description': 'Treat parasitic worms',
                    'subcategories': {
                        'For Roundworm/Hookworm': ['Albendazole', 'Mebendazole', 'Pyrantel'],
                        'For Tapeworms': ['Praziquantel', 'Niclosamide'],
                        'For Filariasis': ['Diethylcarbamazine', 'Ivermectin']
                    }
                },
                'Vaccines': {
                    'description': 'Immunization',
                    'subcategories': {
                        'Killed/Inactivated': ['Hepatitis B', 'Influenza', 'Rabies', 'Polio (IPV)'],
                        'Live Attenuated': ['BCG', 'MMR', 'Varicella', 'Polio (OPV)'],
                        'Toxoids': ['Tetanus', 'Diphtheria'],
                        'Combined': ['DPT', 'MMR']
                    }
                }
            }
        },
        'GASTROINTESTINAL': {
            'name': 'Gastrointestinal System',
            'icon': '🫀',
            'categories': {
                'Peptic Ulcer Drugs': {
                    'description': 'Treat peptic ulcers',
                    'subcategories': {
                        'Acid Secretion Inhibitors': {
                            'subsubcategories': {
                                'H2 Blockers': ['Cimetidine', 'Ranitidine', 'Famotidine'],
                                'PPIs': ['Omeprazole', 'Pantoprazole', 'Lansoprazole', 'Esomeprazole']
                            }
                        },
                        'Ulcer Protectives': ['Sucralfate', 'Colloidal Bismuth'],
                        'Anti-H. pylori': ['Amoxicillin', 'Clarithromycin', 'Metronidazole']
                    }
                },
                'Antacids': {
                    'description': 'Drugs that relieve indigestion and heartburn by neutralizing stomach acid.',
                    'examples': ['Magnesium Hydroxide', 'Aluminum Hydroxide', 'Calcium Carbonate']
                },
                'Antiemetics': {
                    'description': 'Treat nausea and vomiting',
                    'subcategories': {
                        '5-HT3 Antagonists': ['Ondansetron', 'Granisetron', 'Palonosetron'],
                        'H1 Antihistamines': ['Promethazine', 'Diphenhydramine'],
                        'D2 Blockers': ['Metoclopramide', 'Domperidone'],
                        'NK1 Antagonists': ['Aprepitant']
                    }
                },
                'Antidiarrheals': {
                    'description': 'Drugs used for the relief of diarrhea. Two main types of antidiarrheal preparations are simple adsorbent substances and drugs that slow down the contractions of the bowel muscles so that the contents are propelled more slowly.',
                    'subcategories': {
                        'Antimicrobials': ['Norfloxacin', 'Metronidazole'],
                        'Absorbents': ['Kaolin', 'Pectin'],
                        'Antimotility': ['Loperamide', 'Diphenoxylate']
                    }
                },
                'Laxatives': {
                    'description': 'Drugs that increase the frequency and ease of bowel movements, either by stimulating the bowel wall (stimulant laxative), by increasing the bulk of bowel contents (bulk laxative), or by lubricating them (stool-softeners, or bowel movement-softeners). Laxatives may be taken by mouth or directly into the lower bowel as suppositories or enemas. If laxatives are taken regularly, the bowels may ultimately become unable to work properly without them.',
                    'subcategories': {
                        'Bulk Forming': ['Psyllium', 'Methylcellulose'],
                        'Stool Softeners': ['Docusate', 'Liquid Paraffin'],
                        'Osmotic': ['Magnesium Sulfate', 'Lactulose'],
                        'Stimulant': ['Bisacodyl', 'Senna']
                    }
                }
            }
        },
        'RESPIRATORY': {
            'name': 'Respiratory System',
            'icon': '🫁',
            'categories': {
                'Bronchodilators': {
                    'description': 'Drugs that open up the bronchial tubes within the lungs when the tubes have become narrowed by muscle spasm. Bronchodilators ease breathing in diseases such as asthma.',
                    'examples': ['Salbutamol', 'Terbutaline', 'Ipratropium']
                },
                'Expectorants': {
                    'description': 'A drug that stimulates the flow of saliva and promotes coughing to eliminate phlegm from the respiratory tract.',
                    'examples': ['Guaifenesin']
                },
                'Cough Suppressants': {
                    'description': 'Simple cough medicines, which contain substances such as honey, glycerine, or menthol, soothe throat irritation but do not actually suppress coughing. They are most soothing when taken as lozenges and dissolved in the mouth. As liquids they are probably swallowed too quickly to be effective. A few drugs are actually cough suppressants. There are two groups of cough suppressants: those that alter the consistency or production of phlegm such as mucolytics and expectorants; and those that suppress the coughing reflex such as codeine (narcotic cough suppressants), antihistamines, dextromethorphan and isoproterenol (non-narcotic cough suppressants).',
                    'examples': ['Codeine', 'Dextromethorphan', 'Honey', 'Glycerine', 'Menthol']
                },
                'Decongestants': {
                    'description': 'Drugs that reduce swelling of the mucous membranes that line the nose by constricting blood vessels, thus relieving nasal stuffiness.',
                    'examples': ['Pseudoephedrine', 'Phenylephrine', 'Oxymetazoline']
                },
                'Cold Cures': {
                    'description': 'Although there is no drug that can cure a cold, the aches, pains, and fever that accompany a cold can be relieved by aspirin or acetaminophen often accompanied by a decongestant, antihistamine, and sometimes caffeine.',
                    'examples': ['Aspirin', 'Acetaminophen', 'Combination products with decongestants and antihistamines']
                }
            }
        },
        'CNS': {
            'name': 'Central Nervous System',
            'icon': '🧠',
            'categories': {
                'Anticonvulsants': {
                    'description': 'Drugs that prevent epileptic seizures.',
                    'examples': ['Phenytoin', 'Carbamazepine', 'Valproic Acid', 'Lamotrigine']
                },
                'Antidepressants': {
                    'description': 'There are three main groups of mood-lifting antidepressants: tricyclics, monoamine oxidase inhibitors, and selective serotonin reuptake inhibitors (SSRIs).',
                    'subcategories': {
                        'SSRIs': ['Fluoxetine', 'Sertraline', 'Paroxetine'],
                        'Tricyclics': ['Amitriptyline', 'Imipramine'],
                        'MAO Inhibitors': ['Phenelzine', 'Tranylcypromine'],
                        'Others': ['Venlafaxine', 'Bupropion']
                    }
                },
                'Antipsychotics': {
                    'description': 'Drugs used to treat symptoms of severe psychiatric disorders. These drugs are sometimes called major tranquilizers.',
                    'examples': ['Haloperidol', 'Risperidone', 'Olanzapine', 'Quetiapine']
                },
                'Antianxiety/Sedatives': {
                    'description': 'Drugs that suppress anxiety and relax muscles (sometimes called anxiolytics, sedatives, or minor tranquilizers).',
                    'examples': ['Diazepam', 'Lorazepam', 'Alprazolam', 'Buspirone']
                },
                'Sleeping Drugs (Barbiturates & Benzodiazepines)': {
                    'description': 'The two main groups of drugs that are used to induce sleep are benzodiazepines and barbiturates. All such drugs have a sedative effect in low doses and are effective sleeping medications in higher doses. Benzodiazepines drugs are used more widely than barbiturates because they are safer, the side-effects are less marked, and there is less risk of eventual physical dependence.',
                    'subcategories': {
                        'Benzodiazepines': ['Diazepam', 'Lorazepam', 'Temazepam', 'Flurazepam'],
                        'Barbiturates': ['Phenobarbital', 'Secobarbital', 'Pentobarbital'],
                        'Non-Benzodiazepine Hypnotics': ['Zolpidem', 'Zaleplon', 'Eszopiclone']
                    }
                },
                'Tranquilizers': {
                    'description': 'This is a term commonly used to describe any drug that has a calming or sedative effect. However, the drugs that are sometimes called minor tranquilizers should be called antianxiety drugs, and the drugs that are sometimes called major tranquilizers should be called antipsychotics.',
                    'examples': ['See Antianxiety Drugs (minor tranquilizers) and Antipsychotics (major tranquilizers)']
                }
            }
        },
        'CANCER': {
            'name': 'Cancer Treatment',
            'icon': '🎗️',
            'categories': {
                'Cytotoxic Drugs': {
                    'description': 'Kill cancer cells',
                    'subcategories': {
                        'Alkylating Agents': ['Cyclophosphamide', 'Chlorambucil', 'Melphalan'],
                        'Antimetabolites': ['Methotrexate', '5-Fluorouracil', 'Cytarabine'],
                        'Plant Alkaloids': ['Vincristine', 'Vinblastine', 'Paclitaxel'],
                        'Antibiotics': ['Doxorubicin', 'Daunorubicin', 'Bleomycin']
                    }
                },
                'Targeted Therapy': {
                    'examples': ['Imatinib', 'Gefitinib', 'Bevacizumab']
                },
                'Hormonal Therapy': {
                    'examples': ['Tamoxifen', 'Letrozole', 'Flutamide']
                }
            }
        },
        'ENDOCRINE': {
            'name': 'Endocrine System',
            'icon': '⚕️',
            'categories': {
                'Antidiabetic Drugs': {
                    'description': 'Manage blood glucose levels',
                    'subcategories': {
                        'Insulins': {
                            'subsubcategories': {
                                'Rapid Acting': ['Insulin Lispro', 'Insulin Aspart', 'Insulin Glulisine'],
                                'Short Acting': ['Regular Insulin'],
                                'Intermediate Acting': ['NPH Insulin'],
                                'Long Acting': ['Insulin Glargine', 'Insulin Detemir', 'Insulin Degludec'],
                                'Premixed': ['70/30 Insulin', '50/50 Insulin']
                            }
                        },
                        'Oral Hypoglycemics': {
                            'subsubcategories': {
                                'Biguanides': ['Metformin'],
                                'Sulfonylureas': {
                                    '1st Generation': ['Tolbutamide', 'Chlorpropamide'],
                                    '2nd Generation': ['Glipizide', 'Glibenclamide', 'Gliclazide', 'Glimepiride']
                                },
                                'Meglitinides': ['Repaglinide', 'Nateglinide'],
                                'Thiazolidinediones': ['Pioglitazone', 'Rosiglitazone'],
                                'Alpha-Glucosidase Inhibitors': ['Acarbose', 'Miglitol'],
                                'DPP-4 Inhibitors': ['Sitagliptin', 'Vildagliptin', 'Saxagliptin'],
                                'SGLT2 Inhibitors': ['Canagliflozin', 'Dapagliflozin', 'Empagliflozin'],
                                'GLP-1 Agonists': ['Exenatide', 'Liraglutide', 'Dulaglutide']
                            }
                        }
                    }
                },
                'Thyroid Drugs': {
                    'description': 'Manage thyroid function',
                    'subcategories': {
                        'Thyroid Hormones': {
                            'subsubcategories': {
                                'T4 Preparations': ['Levothyroxine'],
                                'T3 Preparations': ['Liothyronine'],
                                'Combined': ['Liotrix']
                            }
                        },
                        'Antithyroid Drugs': {
                            'subsubcategories': {
                                'Thioamides': ['Propylthiouracil', 'Methimazole', 'Carbimazole'],
                                'Iodine': ['Potassium Iodide', 'Lugol\'s Solution'],
                                'Ionic Inhibitors': ['Perchlorate', 'Thiocyanate']
                            }
                        }
                    }
                },
                'Corticosteroids': {
                    'description': 'Hormonal anti-inflammatory agents',
                    'subcategories': {
                        'Glucocorticoids': {
                            'subsubcategories': {
                                'Short Acting': ['Hydrocortisone', 'Cortisone'],
                                'Intermediate Acting': ['Prednisone', 'Prednisolone', 'Methylprednisolone', 'Triamcinolone'],
                                'Long Acting': ['Dexamethasone', 'Betamethasone']
                            }
                        },
                        'Mineralocorticoids': {
                            'examples': ['Fludrocortisone']
                        }
                    }
                },
                'Sex Hormones': {
                    'description': 'Reproductive hormones',
                    'subcategories': {
                        'Estrogens': {
                            'subsubcategories': {
                                'Natural': ['Estradiol', 'Estrone', 'Estriol'],
                                'Synthetic': ['Ethinyl Estradiol', 'Mestranol']
                            }
                        },
                        'Progestins': {
                            'subsubcategories': {
                                'Natural': ['Progesterone'],
                                'Synthetic': ['Medroxyprogesterone', 'Norethindrone', 'Levonorgestrel']
                            }
                        },
                        'Androgens': {
                            'examples': ['Testosterone', 'Methyltestosterone', 'Danazol']
                        },
                        'Antiandrogens': {
                            'examples': ['Flutamide', 'Bicalutamide', 'Cyproterone']
                        },
                        'GnRH Agonists': {
                            'examples': ['Leuprolide', 'Goserelin', 'Triptorelin']
                        },
                        'GnRH Antagonists': {
                            'examples': ['Cetrorelix', 'Ganirelix']
                        }
                    }
                },
                'Growth Hormone & Related': {
                    'description': 'Growth and metabolism',
                    'subcategories': {
                        'Growth Hormone': ['Somatropin', 'Somatrem'],
                        'Somatostatin Analogues': ['Octreotide', 'Lanreotide'],
                        'Prolactin Inhibitors': ['Bromocriptine', 'Cabergoline']
                    }
                },
                'Parathyroid & Bone': {
                    'description': 'Bone metabolism',
                    'subcategories': {
                        'Calcium Regulators': {
                            'subsubcategories': {
                                'Parathyroid Hormone': ['Teriparatide'],
                                'Calcitonin': ['Salmon Calcitonin'],
                                'Bisphosphonates': ['Alendronate', 'Risedronate', 'Zoledronate'],
                                'RANKL Inhibitors': ['Denosumab']
                            }
                        },
                        'Calcium Preparations': {
                            'examples': ['Calcium Carbonate', 'Calcium Citrate', 'Calcium Gluconate']
                        },
                        'Vitamin D': {
                            'examples': ['Cholecalciferol', 'Ergocalciferol', 'Calcitriol']
                        }
                    }
                }
            }
        },
        'GENITOURINARY': {
            'name': 'Genitourinary System',
            'icon': '🔬',
            'categories': {
                'Diuretics': {
                    'description': 'Drugs that increase the quantity of urine produced by the kidneys and passed out of the body, thus ridding the body of excess fluid. Diuretics reduce water logging of the tissues caused by fluid retention in disorders of the heart, kidneys, and liver. They are useful in treating mild cases of high blood pressure.',
                    'subcategories': {
                        'Thiazides': {
                            'examples': ['Hydrochlorothiazide', 'Chlorthalidone', 'Indapamide']
                        },
                        'Loop Diuretics': {
                            'examples': ['Furosemide', 'Bumetanide', 'Torasemide']
                        },
                        'Potassium-Sparing': {
                            'subsubcategories': {
                                'Aldosterone Antagonists': ['Spironolactone', 'Eplerenone'],
                                'Direct Inhibitors': ['Amiloride', 'Triamterene']
                            }
                        },
                        'Carbonic Anhydrase Inhibitors': {
                            'examples': ['Acetazolamide', 'Dorzolamide']
                        },
                        'Osmotic Diuretics': {
                            'examples': ['Mannitol', 'Glycerol']
                        }
                    }
                },
                'Drugs for BPH': {
                    'description': 'Benign Prostatic Hyperplasia',
                    'subcategories': {
                        'Alpha Blockers': ['Tamsulosin', 'Alfuzosin', 'Silodosin'],
                        '5-Alpha Reductase Inhibitors': ['Finasteride', 'Dutasteride'],
                        'Combination': ['Tamsulosin + Dutasteride']
                    }
                },
                'Drugs for Erectile Dysfunction': {
                    'description': 'ED treatment',
                    'subcategories': {
                        'PDE5 Inhibitors': ['Sildenafil', 'Tadalafil', 'Vardenafil', 'Avanafil'],
                        'Prostaglandins': ['Alprostadil']
                    }
                },
                'Urinary Antispasmodics': {
                    'description': 'Overactive bladder',
                    'subcategories': {
                        'Anticholinergics': ['Oxybutynin', 'Tolterodine', 'Solifenacin', 'Darifenacin'],
                        'Beta-3 Agonists': ['Mirabegron']
                    }
                },
                'Uricosurics': {
                    'description': 'Gout treatment',
                    'examples': ['Probenecid', 'Sulfinpyrazone']
                },
                'Xanthine Oxidase Inhibitors': {
                    'description': 'Reduce uric acid',
                    'examples': ['Allopurinol', 'Febuxostat']
                }
            }
        },
        'ANESTHETICS': {
            'name': 'Anesthetics & Analgesics',
            'icon': '💉',
            'categories': {
                'General Anesthetics': {
                    'description': 'Induce unconsciousness',
                    'subcategories': {
                        'Inhalational': {
                            'subsubcategories': {
                                'Volatile Liquids': ['Halothane', 'Isoflurane', 'Sevoflurane', 'Desflurane'],
                                'Gases': ['Nitrous Oxide', 'Xenon']
                            }
                        },
                        'Intravenous': {
                            'subsubcategories': {
                                'Barbiturates': ['Thiopental', 'Methohexital'],
                                'Benzodiazepines': ['Midazolam', 'Diazepam'],
                                'Dissociative': ['Ketamine'],
                                'Propofol': ['Propofol'],
                                'Etomidate': ['Etomidate'],
                                'Opioids': ['Fentanyl', 'Sufentanil', 'Remifentanil']
                            }
                        }
                    }
                },
                'Local Anesthetics': {
                    'description': 'Numb specific areas',
                    'subcategories': {
                        'Esters': {
                            'subsubcategories': {
                                'Short Acting': ['Procaine', 'Chloroprocaine'],
                                'Intermediate Acting': ['Tetracaine']
                            }
                        },
                        'Amides': {
                            'subsubcategories': {
                                'Short Acting': ['Lidocaine', 'Prilocaine'],
                                'Intermediate Acting': ['Mepivacaine'],
                                'Long Acting': ['Bupivacaine', 'Ropivacaine', 'Levobupivacaine']
                            }
                        }
                    }
                },
                'Neuromuscular Blocking Agents': {
                    'description': 'Muscle relaxation during surgery',
                    'subcategories': {
                        'Depolarizing': ['Succinylcholine'],
                        'Non-depolarizing': {
                            'subsubcategories': {
                                'Short Acting': ['Mivacurium'],
                                'Intermediate Acting': ['Atracurium', 'Cisatracurium', 'Rocuronium', 'Vecuronium'],
                                'Long Acting': ['Pancuronium', 'Pipecuronium']
                            }
                        }
                    }
                },
                'Opioid Analgesics': {
                    'description': 'Severe pain management',
                    'subcategories': {
                        'Natural Opioids': ['Morphine', 'Codeine'],
                        'Semisynthetic': ['Hydromorphone', 'Oxycodone', 'Hydrocodone'],
                        'Synthetic': ['Fentanyl', 'Methadone', 'Tramadol', 'Meperidine']
                    }
                },
                'Non-Opioid Analgesics': {
                    'description': 'Mild to moderate pain',
                    'subcategories': {
                        'NSAIDs': {
                            'subsubcategories': {
                                'Non-selective COX Inhibitors': {
                                    'Salicylates': ['Aspirin'],
                                    'Propionic Acids': ['Ibuprofen', 'Naproxen', 'Ketoprofen'],
                                    'Acetic Acids': ['Indomethacin', 'Diclofenac', 'Ketorolac'],
                                    'Enolic Acids': ['Piroxicam', 'Meloxicam'],
                                    'Fenamates': ['Mefenamic Acid']
                                },
                                'Selective COX-2 Inhibitors': ['Celecoxib', 'Rofecoxib', 'Etoricoxib']
                            }
                        },
                        'Acetaminophen': ['Paracetamol']
                    }
                }
            }
        },
        'IMMUNOSUPPRESSANTS': {
            'name': 'Immunosuppressants & Immunomodulators',
            'icon': '🛡️',
            'categories': {
                'Calcineurin Inhibitors': {
                    'description': 'Transplant rejection prevention',
                    'examples': ['Cyclosporine', 'Tacrolimus']
                },
                'mTOR Inhibitors': {
                    'examples': ['Sirolimus', 'Everolimus']
                },
                'Antiproliferatives': {
                    'subcategories': {
                        'Antimetabolites': ['Azathioprine', 'Mycophenolate Mofetil', 'Mycophenolic Acid'],
                        'Alkylating Agents': ['Cyclophosphamide']
                    }
                },
                'Biologics': {
                    'subcategories': {
                        'Monoclonal Antibodies': {
                            'subsubcategories': {
                                'Anti-CD3': ['Muromonab-CD3'],
                                'Anti-CD25': ['Basiliximab', 'Daclizumab'],
                                'Anti-TNF': ['Infliximab', 'Adalimumab', 'Certolizumab'],
                                'Anti-CD20': ['Rituximab'],
                                'Anti-IL-2': ['Daclizumab']
                            }
                        },
                        'Fusion Proteins': {
                            'examples': ['Etanercept', 'Abatacept', 'Belatacept']
                        }
                    }
                },
                'Corticosteroids': {
                    'examples': ['Prednisone', 'Methylprednisolone']
                },
                'Other Immunosuppressants': {
                    'examples': ['Leflunomide', 'Hydroxychloroquine', 'Sulfasalazine']
                }
            }
        },
        'DERMATOLOGICAL': {
            'name': 'Dermatological Drugs',
            'icon': '🧴',
            'categories': {
                'Topical Antibiotics': {
                    'examples': ['Mupirocin', 'Fusidic Acid', 'Neomycin', 'Bacitracin']
                },
                'Topical Antifungals': {
                    'examples': ['Clotrimazole', 'Miconazole', 'Ketoconazole', 'Terbinafine']
                },
                'Topical Corticosteroids': {
                    'subcategories': {
                        'Low Potency': ['Hydrocortisone'],
                        'Medium Potency': ['Triamcinolone', 'Betamethasone'],
                        'High Potency': ['Clobetasol', 'Halobetasol']
                    }
                },
                'Retinoids': {
                    'subcategories': {
                        'Topical': ['Tretinoin', 'Adapalene', 'Tazarotene'],
                        'Systemic': ['Isotretinoin', 'Acitretin']
                    }
                },
                'Drugs for Acne': {
                    'subcategories': {
                        'Topical': ['Benzoyl Peroxide', 'Tretinoin', 'Adapalene', 'Azelaic Acid'],
                        'Systemic': ['Doxycycline', 'Minocycline', 'Isotretinoin']
                    }
                },
                'Antipruritics': {
                    'examples': ['Calamine', 'Menthol', 'Camphor', 'Pramoxine']
                },
                'Keratolytics': {
                    'examples': ['Salicylic Acid', 'Urea', 'Lactic Acid']
                },
                'Psoriasis Drugs': {
                    'subcategories': {
                        'Topical': ['Calcipotriol', 'Tacrolimus', 'Pimecrolimus'],
                        'Systemic': ['Methotrexate', 'Cyclosporine', 'Acitretin'],
                        'Biologics': ['Etanercept', 'Adalimumab', 'Infliximab']
                    }
                }
            }
        },
        'OPHTHALMIC': {
            'name': 'Ophthalmic Drugs',
            'icon': '👁️',
            'categories': {
                'Antibiotics': {
                    'examples': ['Chloramphenicol', 'Ciprofloxacin', 'Ofloxacin', 'Moxifloxacin']
                },
                'Antivirals': {
                    'examples': ['Acyclovir', 'Ganciclovir']
                },
                'Antifungals': {
                    'examples': ['Natamycin', 'Amphotericin B']
                },
                'Anti-inflammatory': {
                    'subcategories': {
                        'Corticosteroids': ['Prednisolone', 'Dexamethasone'],
                        'NSAIDs': ['Diclofenac', 'Ketorolac', 'Nepafenac']
                    }
                },
                'Glaucoma Drugs': {
                    'subcategories': {
                        'Beta Blockers': ['Timolol', 'Betaxolol'],
                        'Prostaglandin Analogues': ['Latanoprost', 'Travoprost', 'Bimatoprost'],
                        'Carbonic Anhydrase Inhibitors': ['Dorzolamide', 'Brinzolamide'],
                        'Alpha Agonists': ['Brimonidine', 'Apraclonidine'],
                        'Cholinergics': ['Pilocarpine', 'Carbachol'],
                        'Combination': ['Timolol + Dorzolamide', 'Timolol + Brimonidine']
                    }
                },
                'Mydriatics': {
                    'examples': ['Tropicamide', 'Phenylephrine', 'Cyclopentolate']
                },
                'Miotics': {
                    'examples': ['Pilocarpine', 'Carbachol']
                },
                'Artificial Tears': {
                    'examples': ['Carboxymethylcellulose', 'Hypromellose', 'Polyethylene Glycol']
                }
            }
        },
        'ENT': {
            'name': 'Ear, Nose & Throat',
            'icon': '👂',
            'categories': {
                'Nasal Decongestants': {
                    'subcategories': {
                        'Topical': ['Oxymetazoline', 'Xylometazoline', 'Phenylephrine'],
                        'Oral': ['Pseudoephedrine', 'Phenylephrine']
                    }
                },
                'Nasal Corticosteroids': {
                    'examples': ['Beclomethasone', 'Fluticasone', 'Mometasone', 'Budesonide']
                },
                'Antihistamines (Nasal)': {
                    'examples': ['Azelastine', 'Olopatadine']
                },
                'Ear Drops': {
                    'subcategories': {
                        'Antibiotics': ['Ciprofloxacin', 'Ofloxacin'],
                        'Antifungals': ['Clotrimazole'],
                        'Wax Softeners': ['Carbamide Peroxide', 'Glycerol']
                    }
                },
                'Throat Preparations': {
                    'examples': ['Benzocaine', 'Lidocaine', 'Chlorhexidine']
                }
            }
        },
        'OTHER': {
            'name': 'Other Categories',
            'icon': '💉',
            'categories': {
                'Antihistamines': {
                    'description': 'Treat allergies',
                    'subcategories': {
                        '1st Generation': ['Chlorpheniramine', 'Diphenhydramine', 'Promethazine', 'Cyproheptadine'],
                        '2nd Generation': ['Loratadine', 'Cetirizine', 'Fexofenadine', 'Desloratadine']
                    }
                },
                'Muscle Relaxants': {
                    'description': 'Relieve muscle spasm',
                    'subcategories': {
                        'Centrally Acting': ['Baclofen', 'Tizanidine', 'Cyclobenzaprine', 'Methocarbamol'],
                        'Direct Acting': ['Dantrolene']
                    }
                },
                'Vitamins & Minerals': {
                    'description': 'Nutritional supplements',
                    'subcategories': {
                        'Water Soluble': {
                            'B Complex': ['Thiamine (B1)', 'Riboflavin (B2)', 'Niacin (B3)', 'Pyridoxine (B6)', 'Cyanocobalamin (B12)', 'Folic Acid'],
                            'Vitamin C': ['Ascorbic Acid']
                        },
                        'Fat Soluble': {
                            'examples': ['Vitamin A', 'Vitamin D', 'Vitamin E', 'Vitamin K']
                        },
                        'Minerals': {
                            'examples': ['Calcium', 'Iron', 'Zinc', 'Magnesium', 'Potassium']
                        }
                    }
                },
                'Peripheral Vascular Drugs': {
                    'description': 'Treat vascular diseases',
                    'examples': ['Pentoxifylline', 'Cilostazol', 'Naftidrofuryl']
                },
                'Antidotes': {
                    'description': 'Poison treatment',
                    'subcategories': {
                        'Heavy Metals': ['Dimercaprol', 'EDTA', 'Penicillamine'],
                        'Opioids': ['Naloxone', 'Naltrexone'],
                        'Benzodiazepines': ['Flumazenil'],
                        'Anticholinesterase': ['Atropine', 'Pralidoxime'],
                        'Heparin': ['Protamine'],
                        'Warfarin': ['Vitamin K', 'Fresh Frozen Plasma']
                    }
                },
                'Contrast Media': {
                    'description': 'Medical imaging',
                    'subcategories': {
                        'Iodinated': ['Iohexol', 'Iopamidol', 'Iodixanol'],
                        'Gadolinium': ['Gadopentetate', 'Gadodiamide'],
                        'Barium': ['Barium Sulfate']
                    }
                },
                'Diagnostic Agents': {
                    'examples': ['Tuberculin', 'Allergen Extracts']
                },
                'Electrolytes': {
                    'description': 'Fluid and electrolyte balance',
                    'examples': ['Sodium Chloride', 'Potassium Chloride', 'Calcium Gluconate', 'Magnesium Sulfate']
                },
                'Blood Products': {
                    'description': 'Blood components',
                    'examples': ['Whole Blood', 'Packed Red Cells', 'Fresh Frozen Plasma', 'Platelets', 'Cryoprecipitate']
                }
            }
        }
    }
    
    # Comprehensive category mapping - maps guide category names to database category codes
    # This ensures ALL drugs uploaded to inventory with categories appear in the guide
    category_mapping = {
        'Analgesics': ['analgesic', 'anti_inflammatory'],
        'Antipyretics': ['antipyretic', 'analgesic'],
        'Anti-Inflammatories': ['anti_inflammatory', 'analgesic', 'corticosteroid'],
        'Antihypertensives': ['antihypertensive', 'diuretic', 'beta_blocker'],
        'Antianginal Drugs': ['beta_blocker', 'antihypertensive'],
        'Antiarrhythmics': ['antiarrhythmic', 'beta_blocker'],
        'Anticoagulants': ['anticoagulant'],
        'Thrombolytics (Fibrinolytics)': ['thrombolytic'],
        'Antiplatelet Drugs': ['anticoagulant'],
        'Drugs for CHF': ['antihypertensive', 'diuretic', 'beta_blocker'],
        'Hypolipidaemic Drugs': ['other'],  # May need specific category
        'Haematinics': ['vitamin'],  # Iron, B12, Folic acid
        'Coagulants': ['other'],
        'Antibiotics': ['antibiotic', 'antibacterial'],
        'Antibacterials': ['antibacterial', 'antibiotic'],
        'Antivirals': ['antiviral'],
        'Antifungals': ['antifungal'],
        'Antacids': ['antacid'],
        'Antiemetics': ['antiemetic'],
        'Antidiarrheals': ['antidiarrheal'],
        'Laxatives': ['laxative'],
        'Bronchodilators': ['bronchodilator'],
        'Expectorants': ['expectorant'],
        'Cough Suppressants': ['cough_suppressant', 'expectorant'],
        'Decongestants': ['decongestant'],
        'Cold Cures': ['cold_cure', 'antipyretic', 'decongestant', 'antihistamine'],
        'Anticonvulsants': ['anticonvulsant'],
        'Antidepressants': ['antidepressant'],
        'Antipsychotics': ['antipsychotic'],
        'Antianxiety/Sedatives': ['antianxiety', 'sedative', 'sleeping_drug', 'tranquilizer'],
        'Sleeping Drugs (Barbiturates & Benzodiazepines)': ['sleeping_drug', 'barbiturate', 'antianxiety', 'sedative'],
        'Tranquilizers': ['tranquilizer', 'antianxiety', 'antipsychotic', 'sedative'],
        'Antihistamines': ['antihistamine'],
        'Corticosteroids': ['corticosteroid', 'anti_inflammatory', 'immunosuppressive'],
        'Muscle Relaxants': ['muscle_relaxant', 'antianxiety'],
        'Diuretics': ['diuretic', 'antihypertensive'],
        'Antidiabetic Drugs': ['oral_hypoglycemic', 'hormone'],
        'Thyroid Drugs': ['hormone'],
        'Sex Hormones': ['female_sex_hormone', 'male_sex_hormone', 'hormone'],
        'Vitamins & Minerals': ['vitamin'],
        'Cytotoxic Drugs': ['cytotoxic', 'antineoplastic'],
        'Targeted Therapy': ['antineoplastic'],
        'Hormonal Therapy': ['female_sex_hormone', 'male_sex_hormone', 'hormone'],
        'Immunosuppressives': ['immunosuppressive', 'corticosteroid', 'cytotoxic'],
    }
    
    # OPTIMIZATION: Get ALL data in minimal queries instead of N+1 queries
    # Performance improvement: 100+ queries → 2 queries (50x faster!)
    from django.db.models import Sum
    
    # Query 1: Get all stock totals in ONE query
    stock_totals = PharmacyStock.objects.filter(
        is_deleted=False
    ).values('drug_id').annotate(
        total_stock=Sum('quantity_on_hand')
    )
    
    # Create a dictionary for O(1) lookup: drug_id -> total_stock
    stock_dict = {item['drug_id']: (item['total_stock'] or 0) for item in stock_totals}
    
    # Query 2: Get ALL active drugs ONCE - much faster than querying per category
    all_active_drugs = list(Drug.objects.filter(
        is_active=True,
        is_deleted=False
    ).exclude(category='').select_related().only(
        'id', 'name', 'generic_name', 'strength', 'form', 'unit_price', 'category'
    ))
    
    # Group drugs by category in memory for O(1) lookup
    drugs_by_category_dict = {}
    for drug in all_active_drugs:
        category = drug.category
        if category not in drugs_by_category_dict:
            drugs_by_category_dict[category] = []
        drugs_by_category_dict[category].append(drug)
    
    # Helper function to build drug dict with stock info
    def build_drug_dict(drug, stock_dict):
        total_stock = stock_dict.get(drug.id, 0)
        has_stock = total_stock > 0
        
        if total_stock == 0:
            stock_status = 'out_of_stock'
            stock_label = 'Out of Stock'
        elif total_stock <= 10:
            stock_status = 'low_stock'
            stock_label = f'Low Stock ({int(total_stock)})'
        else:
            stock_status = 'in_stock'
            stock_label = f'In Stock ({int(total_stock)})'
        
        return {
            'id': str(drug.id),
            'name': drug.name,
            'generic_name': drug.generic_name,
            'strength': drug.strength,
            'form': drug.form,
            'unit_price': float(drug.unit_price),
            'category': drug.category,
            'category_display': drug.get_category_display(),
            'stock_quantity': int(total_stock),
            'has_stock': has_stock,
            'stock_status': stock_status,
            'stock_label': stock_label,
        }
    
    # Get actual drugs from database for each category with stock information
    # OPTIMIZED: Use pre-fetched and grouped drugs instead of querying
    for system_key, system_data in drug_classification.items():
        for cat_key, cat_data in system_data.get('categories', {}).items():
            # Get matching categories
            db_categories = category_mapping.get(cat_key, [])
            
            if db_categories:
                # OPTIMIZED: Get drugs from pre-grouped dictionary instead of querying
                drugs = []
                for cat in db_categories:
                    if cat in drugs_by_category_dict:
                        drugs.extend(drugs_by_category_dict[cat])
                
                # Remove duplicates (in case a drug matches multiple categories)
                seen_ids = set()
                unique_drugs = []
                for drug in drugs:
                    if drug.id not in seen_ids:
                        seen_ids.add(drug.id)
                        unique_drugs.append(drug)
                
                # OPTIMIZED: Build drug dicts using helper function
                drugs_with_stock = [build_drug_dict(drug, stock_dict) for drug in unique_drugs]
                
                # Sort by stock status (in stock first) then by name
                drugs_with_stock.sort(key=lambda x: (not x['has_stock'], x['name'].lower()))
                
                cat_data['drugs_in_stock'] = drugs_with_stock
                cat_data['drugs_count'] = len(drugs_with_stock)
                cat_data['in_stock_count'] = sum(1 for d in drugs_with_stock if d['has_stock'])
                
                # Find alternative categories if no drugs available
                if not drugs_with_stock or cat_data['in_stock_count'] == 0:
                    # Suggest alternatives from related categories
                    alternatives = []
                    if cat_key == 'Antibiotics':
                        alternatives = ['Antibacterials', 'Antifungals']
                    elif cat_key == 'Analgesics':
                        alternatives = ['Anti-Inflammatories', 'Antipyretics']
                    elif cat_key == 'Antihypertensives':
                        alternatives = ['Diuretics', 'Beta-Blockers']
                    elif cat_key == 'Antidepressants':
                        alternatives = ['Antianxiety/Sedatives', 'Antipsychotics']
                    
                    cat_data['alternatives'] = alternatives
    
    # Add a section showing ALL drugs by their actual database category
    # This ensures drugs uploaded with categories appear even if they don't match guide categories
    # OPTIMIZED: Use pre-fetched drugs instead of querying again
    all_drugs_by_category = {}
    
    # Sort all_active_drugs by category and name for consistent output
    sorted_drugs = sorted(all_active_drugs, key=lambda d: (d.category or '', d.name or ''))
    
    for drug in sorted_drugs:
        category_code = drug.category
        if not category_code:
            continue
            
        category_display = drug.get_category_display()
        
        if category_code not in all_drugs_by_category:
            all_drugs_by_category[category_code] = {
                'name': category_display,
                'code': category_code,
                'drugs': []
            }
        
        # OPTIMIZED: Use helper function to build drug dict
        all_drugs_by_category[category_code]['drugs'].append(build_drug_dict(drug, stock_dict))
    
    # Sort drugs within each category by stock status then name
    for cat_code, cat_info in all_drugs_by_category.items():
        cat_info['drugs'].sort(key=lambda x: (not x['has_stock'], x['name'].lower()))
        cat_info['total_count'] = len(cat_info['drugs'])
        cat_info['in_stock_count'] = sum(1 for d in cat_info['drugs'] if d['has_stock'])
    
    context = {
        'drug_classification': drug_classification,
        'all_drugs_by_category': all_drugs_by_category,  # All drugs organized by database category
        'page_title': 'Drug Classification Guide',
        'page_description': 'Comprehensive drug reference guide for doctors and pharmacy staff',
        'encounter_id': encounter_id  # Pass encounter_id to template for prescription linking
    }
    
    return render(request, 'hospital/drug_classification_guide.html', context)


@login_required
def drugs_by_category(request, category_code):
    """
    Get drugs by category code for prescription
    Shows available drugs in inventory with stock levels
    OPTIMIZED: Uses single query for stock totals instead of N+1 queries
    """
    from hospital.models import Drug, PharmacyStock
    from django.db.models import Sum
    
    # Get drugs in this category
    drugs = Drug.objects.filter(
        category=category_code,
        is_active=True,
        is_deleted=False
    ).order_by('name')
    
    # OPTIMIZATION: Get all stock totals in ONE query
    drug_ids = [drug.id for drug in drugs]
    stock_totals = PharmacyStock.objects.filter(
        drug_id__in=drug_ids,
        is_deleted=False
    ).values('drug_id').annotate(
        total_stock=Sum('quantity_on_hand')
    )
    
    # Create dictionary for O(1) lookup
    stock_dict = {item['drug_id']: (item['total_stock'] or 0) for item in stock_totals}
    
    # Get stock information - OPTIMIZED: use dictionary lookup
    drugs_list = []
    for drug in drugs:
        total_stock = stock_dict.get(drug.id, 0)
        
        drugs_list.append({
            'id': str(drug.id),
            'name': drug.name,
            'generic_name': drug.generic_name or '',
            'strength': drug.strength,
            'form': drug.form,
            'unit_price': float(drug.unit_price),
            'stock_quantity': int(total_stock),
            'has_stock': total_stock > 0,
            'stock_status': 'in_stock' if total_stock > 10 else ('low_stock' if total_stock > 0 else 'out_of_stock'),
        })
    
    # Get category display name
    category_display = dict(Drug.CATEGORIES).get(category_code, category_code)
    
    # Get encounter_id if provided (for prescription)
    encounter_id = request.GET.get('encounter_id')
    
    context = {
        'drugs': drugs_list,
        'category_code': category_code,
        'category_display': category_display,
        'encounter_id': encounter_id,
        'total_drugs': len(drugs_list),
        'in_stock_count': sum(1 for d in drugs_list if d['has_stock']),
    }
    
    return render(request, 'hospital/drugs_by_category.html', context)


@login_required
def api_drug_detail(request, drug_id):
    """
    API endpoint to get drug details by ID
    Returns JSON with drug information including category
    """
    from hospital.models import Drug, PharmacyStock
    from django.db.models import Sum
    
    try:
        drug = Drug.objects.get(pk=drug_id, is_deleted=False)
        
        # Get stock information
        total_stock = PharmacyStock.objects.filter(
            drug=drug,
            is_deleted=False
        ).aggregate(total=Sum('quantity_on_hand'))['total'] or 0
        
        return JsonResponse({
            'id': str(drug.id),
            'name': drug.name,
            'generic_name': drug.generic_name or '',
            'strength': drug.strength,
            'form': drug.form,
            'category': drug.category,
            'category_display': drug.get_category_display(),
            'unit_price': float(drug.unit_price),
            'atc_code': drug.atc_code or '',
            'is_controlled': drug.is_controlled,
            'stock_quantity': int(total_stock),
            'has_stock': total_stock > 0,
        })
    except Drug.DoesNotExist:
        return JsonResponse({'error': 'Drug not found'}, status=404)


@login_required
def api_drugs_by_category(request, category_code):
    """
    API endpoint to get drugs by category for AJAX requests
    Returns JSON with drug list and stock information
    OPTIMIZED: Uses single query for stock totals instead of N+1 queries
    """
    from hospital.models import Drug, PharmacyStock
    from django.db.models import Sum
    
    # Get drugs in this category
    drugs = Drug.objects.filter(
        category=category_code,
        is_active=True,
        is_deleted=False
    ).order_by('name')[:50]  # Limit to 50
    
    # OPTIMIZATION: Get all stock totals in ONE query
    drug_ids = [drug.id for drug in drugs]
    stock_totals = PharmacyStock.objects.filter(
        drug_id__in=drug_ids,
        is_deleted=False
    ).values('drug_id').annotate(
        total_stock=Sum('quantity_on_hand')
    )
    
    # Create dictionary for O(1) lookup
    stock_dict = {item['drug_id']: (item['total_stock'] or 0) for item in stock_totals}
    
    # Get stock information - OPTIMIZED: use dictionary lookup
    drugs_list = []
    for drug in drugs:
        total_stock = stock_dict.get(drug.id, 0)
        
        drugs_list.append({
            'id': str(drug.id),
            'name': drug.name,
            'generic_name': drug.generic_name or '',
            'strength': drug.strength,
            'form': drug.form,
            'unit_price': float(drug.unit_price),
            'stock_quantity': int(total_stock),
            'has_stock': total_stock > 0,
            'stock_status': 'in_stock' if total_stock > 10 else ('low_stock' if total_stock > 0 else 'out_of_stock'),
        })
    
    # Find alternative categories
    alternatives = []
    category_mapping = {
        'antibiotic': ['antibacterial', 'antifungal'],
        'analgesic': ['anti_inflammatory', 'antipyretic'],
        'antihypertensive': ['diuretic', 'beta_blocker'],
        'antidepressant': ['antianxiety', 'antipsychotic'],
    }
    alternatives_codes = category_mapping.get(category_code, [])
    if alternatives_codes:
        alt_drugs = Drug.objects.filter(
            category__in=alternatives_codes,
            is_active=True,
            is_deleted=False
        )[:5]
        
        # OPTIMIZATION: Get stock for alternatives in one query
        alt_drug_ids = [d.id for d in alt_drugs]
        alt_stock_totals = PharmacyStock.objects.filter(
            drug_id__in=alt_drug_ids,
            is_deleted=False
        ).values('drug_id').annotate(
            total_stock=Sum('quantity_on_hand')
        )
        alt_stock_dict = {item['drug_id']: (item['total_stock'] or 0) for item in alt_stock_totals}
        
        for alt_drug in alt_drugs:
            alt_stock = alt_stock_dict.get(alt_drug.id, 0)
            if alt_stock > 0:
                alternatives.append({
                    'id': str(alt_drug.id),
                    'name': alt_drug.name,
                    'category': alt_drug.get_category_display(),
                    'stock_quantity': int(alt_stock),
                })
    
    return JsonResponse({
        'drugs': drugs_list,
        'category_code': category_code,
        'category_display': dict(Drug.CATEGORIES).get(category_code, category_code),
        'total_drugs': len(drugs_list),
        'in_stock_count': sum(1 for d in drugs_list if d['has_stock']),
        'alternatives': alternatives[:5],  # Limit to 5 alternatives
    })


@login_required
def api_search_active_encounters(request):
    """
    API endpoint to search for active encounters for prescription
    Returns JSON with encounter list for patient selection
    """
    # Use module-level imports (Q is imported at line 7)
    from hospital.models import Encounter
    from django.utils import timezone
    from datetime import timedelta
    
    search_query = request.GET.get('q', '').strip()
    
    # Get active encounters from last 7 days
    recent_cutoff = timezone.now() - timedelta(days=7)
    
    encounters = Encounter.objects.filter(
        status='active',
        is_deleted=False,
        started_at__gte=recent_cutoff
    ).select_related('patient', 'provider').order_by('-started_at')
    
    # Apply search filter (Q is imported at module level, line 7)
    if search_query:
        encounters = encounters.filter(
            Q(patient__first_name__icontains=search_query) |
            Q(patient__last_name__icontains=search_query) |
            Q(patient__mrn__icontains=search_query) |
            Q(chief_complaint__icontains=search_query)
        )
    
    # Limit to 20 results
    encounters = encounters[:20]
    
    encounters_list = []
    for encounter in encounters:
        encounters_list.append({
            'id': str(encounter.id),
            'patient_name': encounter.patient.full_name,
            'patient_mrn': encounter.patient.mrn,
            'patient_age': encounter.patient.age,
            'patient_gender': encounter.patient.get_gender_display(),
            'encounter_type': encounter.get_encounter_type_display(),
            'chief_complaint': encounter.chief_complaint or 'No complaint recorded',
            'started_at': encounter.started_at.strftime('%Y-%m-%d %H:%M'),
            'provider_name': encounter.provider.user.get_full_name() if encounter.provider else 'N/A',
        })
    
    return JsonResponse({
        'encounters': encounters_list,
        'count': len(encounters_list),
    })

