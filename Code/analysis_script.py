import pandas as pd
import numpy as np
from datetime import datetime
import os

def analyze_ckd_data(filepath):
    # Read the CSV file
    df = pd.read_csv(filepath)
    
    # Initialize results dictionary
    stats = {
        'total_patients': len(df),
        'staging_mismatch': 0,
        'contraindicated_drugs': 0,
        'dose_adjustment_needed': 0,
        'uncoded_ckd': 0,
        'stage_distribution': {},
        'bp_not_at_target': 0,
        'anaemia_count': 0,
        'vitamin_d_deficient': 0,
        'high_cv_risk': 0,
        'referral_needed': 0,
        'aki_cases': 0,
        'priority_distribution': {},
        'age_stats': {},
        'gender_distribution': {},
        'proteinuria_distribution': {},
        'bp_classification': {},
        'egfr_stats': {}
    }
    
    for _, row in df.iterrows():
        # Original staging checks
        emis_code = str(row['EMIS_CKD_Code']).lower()
        current_stage = str(row['CKD_Stage']).lower()
        
        if 'stage' in emis_code and 'stage' in current_stage:
            emis_stage = ''.join(filter(str.isdigit, emis_code))
            current_stage_num = ''.join(filter(str.isdigit, current_stage))
            if emis_stage != current_stage_num:
                stats['staging_mismatch'] += 1
        
        if ('No EMIS' in str(row['EMIS_CKD_Code']) or pd.isna(row['EMIS_CKD_Code'])) and 'stage' in current_stage.lower():
            stats['uncoded_ckd'] += 1
            
        # Track stage distribution
        if not pd.isna(row['CKD_Stage']):
            if row['CKD_Stage'] in stats['stage_distribution']:
                stats['stage_distribution'][row['CKD_Stage']] += 1
            else:
                stats['stage_distribution'][row['CKD_Stage']] = 1

        # Blood Pressure Analysis
        if row['BP_Flag'] == 'Above Target':
            stats['bp_not_at_target'] += 1
            
        if row['BP_Classification'] in stats['bp_classification']:
            stats['bp_classification'][row['BP_Classification']] += 1
        else:
            stats['bp_classification'][row['BP_Classification']] = 1
        
        # Anaemia Cases
        if 'Anaemia' in str(row['Anaemia_Classification']):
            stats['anaemia_count'] += 1
            
        # Vitamin D Status
        if row['Vitamin_D_Flag'] == 'Deficient':
            stats['vitamin_d_deficient'] += 1
            
        # Cardiovascular Risk
        if row['CV_Risk'] == 'High Risk':
            stats['high_cv_risk'] += 1
            
        # Nephrology Referrals Needed
        if str(row['Nephrology_Referral']) == 'Indicated on the basis of risk calculation':
            stats['referral_needed'] += 1
            
        # AKI Cases
        if row['AKI_Flag'] == 'AKI':
            stats['aki_cases'] += 1
            
        # Priority Distribution
        if row['Priority'] in stats['priority_distribution']:
            stats['priority_distribution'][row['Priority']] += 1
        else:
            stats['priority_distribution'][row['Priority']] = 1
            
        # Gender Distribution
        if row['Gender'] in stats['gender_distribution']:
            stats['gender_distribution'][row['Gender']] += 1
        else:
            stats['gender_distribution'][row['Gender']] = 1
            
        # Proteinuria Distribution
        if row['CKD_ACR'] in stats['proteinuria_distribution']:
            stats['proteinuria_distribution'][row['CKD_ACR']] += 1
        else:
            stats['proteinuria_distribution'][row['CKD_ACR']] = 1

    # Count contraindicated medications and dose adjustments (excluding "No contraindications" and "No adjustments needed")
    stats['contraindicated_drugs'] = len(df[df['contraindicated_prescribed'].notna() & 
                                        (df['contraindicated_prescribed'] != 'No contraindications')])
    stats['dose_adjustment_needed'] = len(df[df['dose_adjustment_prescribed'].notna() & 
                                        (df['dose_adjustment_prescribed'] != 'No adjustments needed')])
        
    # Calculate age statistics
    stats['age_stats'] = {
        'mean': df['Age'].mean(),
        'median': df['Age'].median(),
        'min': df['Age'].min(),
        'max': df['Age'].max()
    }
    
    # Calculate eGFR statistics
    stats['egfr_stats'] = {
        'mean': df['eGFR'].mean(),
        'median': df['eGFR'].median(),
        'min': df['eGFR'].min(),
        'max': df['eGFR'].max()
    }

    return stats

def print_results(stats):
    """Print analysis results to console"""
    print("\n=== CKD Patient Analysis Results ===")
    total = stats['total_patients']
    print(f"Total number of patients: {total}")
    
    print("\nStaging Discrepancies:")
    print(f"Number of patients with EMIS staging mismatch: {stats['staging_mismatch']} ({(stats['staging_mismatch']/total*100):.1f}%)")
    print(f"Number of patients with uncoded CKD: {stats['uncoded_ckd']} ({(stats['uncoded_ckd']/total*100):.1f}%)")
    
    print("\nCKD Stage Distribution:")
    for stage, count in sorted(stats['stage_distribution'].items()):
        print(f"{stage}: {count} patients ({(count/total*100):.1f}%)")
    
    print("\nClinical Indicators:")
    print(f"Patients with BP above target: {stats['bp_not_at_target']} ({(stats['bp_not_at_target']/total*100):.1f}%)")
    print(f"Patients with Anaemia: {stats['anaemia_count']} ({(stats['anaemia_count']/total*100):.1f}%)")
    print(f"Patients with Vitamin D deficiency: {stats['vitamin_d_deficient']} ({(stats['vitamin_d_deficient']/total*100):.1f}%)")
    print(f"Patients with high CV risk: {stats['high_cv_risk']} ({(stats['high_cv_risk']/total*100):.1f}%)")
    print(f"Patients needing nephrology referral: {stats['referral_needed']} ({(stats['referral_needed']/total*100):.1f}%)")
    print(f"Patients with AKI: {stats['aki_cases']} ({(stats['aki_cases']/total*100):.1f}%)")
    
    print("\nMedication Issues:")
    print(f"Patients on contraindicated medications: {stats['contraindicated_drugs']} ({(stats['contraindicated_drugs']/total*100):.1f}%)")
    print(f"Patients requiring medication dose adjustments: {stats['dose_adjustment_needed']} ({(stats['dose_adjustment_needed']/total*100):.1f}%)")
    
    print("\nAge Statistics:")
    print(f"Mean age: {stats['age_stats']['mean']:.1f}")
    print(f"Median age: {stats['age_stats']['median']:.1f}")
    print(f"Age range: {stats['age_stats']['min']:.0f} - {stats['age_stats']['max']:.0f}")
    
    print("\neGFR Statistics:")
    print(f"Mean eGFR: {stats['egfr_stats']['mean']:.1f}")
    print(f"Median eGFR: {stats['egfr_stats']['median']:.1f}")
    print(f"eGFR range: {stats['egfr_stats']['min']:.0f} - {stats['egfr_stats']['max']:.0f}")
    
    print("\nGender Distribution:")
    for gender, count in stats['gender_distribution'].items():
        print(f"{gender}: {count} patients ({(count/stats['total_patients']*100):.1f}%)")
    
    print("\nProteinuria Distribution:")
    for category, count in sorted(stats['proteinuria_distribution'].items()):
        print(f"{category}: {count} patients ({(count/stats['total_patients']*100):.1f}%)")
    
    print("\nBP Classification:")
    bp_items = [(str(bp_class), count) for bp_class, count in stats['bp_classification'].items()]
    for bp_class, count in sorted(bp_items):
        print(f"{bp_class}: {count} patients ({(count/stats['total_patients']*100):.1f}%)")
    
    print("\nPriority Distribution:")
    for priority, count in sorted(stats['priority_distribution'].items()):
        print(f"{priority}: {count} patients ({(count/stats['total_patients']*100):.1f}%)")

def save_results(stats, output_path):
    """Save analysis results to a text file"""
    total = stats['total_patients']
    with open(output_path, 'w') as f:
        f.write("=== CKD Patient Analysis Results ===\n")
        f.write(f"Total number of patients: {total}\n")
        
        f.write("\nStaging Discrepancies:\n")
        f.write(f"Number of patients with EMIS staging mismatch: {stats['staging_mismatch']} ({(stats['staging_mismatch']/total*100):.1f}%)\n")
        f.write(f"Number of patients with uncoded CKD: {stats['uncoded_ckd']} ({(stats['uncoded_ckd']/total*100):.1f}%)\n")
        
        f.write("\nClinical Indicators:\n")
        f.write(f"Patients with BP above target: {stats['bp_not_at_target']} ({(stats['bp_not_at_target']/total*100):.1f}%)\n")
        f.write(f"Patients with Anaemia: {stats['anaemia_count']} ({(stats['anaemia_count']/total*100):.1f}%)\n")
        f.write(f"Patients with Vitamin D deficiency: {stats['vitamin_d_deficient']} ({(stats['vitamin_d_deficient']/total*100):.1f}%)\n")
        f.write(f"Patients with high CV risk: {stats['high_cv_risk']} ({(stats['high_cv_risk']/total*100):.1f}%)\n")
        f.write(f"Patients needing nephrology referral: {stats['referral_needed']} ({(stats['referral_needed']/total*100):.1f}%)\n")
        f.write(f"Patients with AKI: {stats['aki_cases']} ({(stats['aki_cases']/total*100):.1f}%)\n")
        
        f.write("\nMedication Issues:\n")
        f.write(f"Patients on contraindicated medications: {stats['contraindicated_drugs']} ({(stats['contraindicated_drugs']/total*100):.1f}%)\n")
        f.write(f"Patients requiring medication dose adjustments: {stats['dose_adjustment_needed']} ({(stats['dose_adjustment_needed']/total*100):.1f}%)\n")
             
        f.write("\nAge Statistics:\n")
        f.write(f"Mean age: {stats['age_stats']['mean']:.1f}\n")
        f.write(f"Median age: {stats['age_stats']['median']:.1f}\n")
        f.write(f"Age range: {stats['age_stats']['min']:.0f} - {stats['age_stats']['max']:.0f}\n")
        
        f.write("\neGFR Statistics:\n")
        f.write(f"Mean eGFR: {stats['egfr_stats']['mean']:.1f}\n")
        f.write(f"Median eGFR: {stats['egfr_stats']['median']:.1f}\n")
        f.write(f"eGFR range: {stats['egfr_stats']['min']:.0f} - {stats['egfr_stats']['max']:.0f}\n")
        
        f.write("\nGender Distribution:\n")
        for gender, count in stats['gender_distribution'].items():
            f.write(f"{gender}: {count} patients ({(count/stats['total_patients']*100):.1f}%)\n")
        
        f.write("\nProteinuria Distribution:\n")
        for category, count in sorted(stats['proteinuria_distribution'].items()):
            f.write(f"{category}: {count} patients ({(count/stats['total_patients']*100):.1f}%)\n")
        
        f.write("\nBP Classification:\n")
        bp_items = [(str(bp_class), count) for bp_class, count in stats['bp_classification'].items()]
        for bp_class, count in sorted(bp_items):
            f.write(f"{bp_class}: {count} patients ({(count/stats['total_patients']*100):.1f}%)\n")
    
        f.write("\nPriority Distribution:\n")
        for priority, count in sorted(stats['priority_distribution'].items()):
            f.write(f"{priority}: {count} patients ({(count/stats['total_patients']*100):.1f}%)\n")

# Update the main block to include saving to file
if __name__ == "__main__":
    # Get current date in YYYY-MM-DD format
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    # Construct filepath using current date
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    filepath = os.path.join(
        base_path,
        "Patient_Summaries",
        current_date,
        f"data_check_{current_date}.csv"
    )
    
    # Construct output filepath
    output_path = os.path.join(
        base_path,
        "Patient_Summaries",
        current_date,
        f"analysis_results_{current_date}.txt"
    )
    
    # Check if input file exists
    if not os.path.exists(filepath):
        print(f"Error: File not found at {filepath}")
        exit(1)
    
    # Run analysis and save results
    results = analyze_ckd_data(filepath)
    save_results(results, output_path)
    print(f"Analysis results saved to: {output_path}")
    
    # Also print results to console
    print_results(results)
    # Get current date in YYYY-MM-DD format
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    # Construct filepath using current date
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    filepath = os.path.join(
        base_path,
        "Patient_Summaries",
        current_date,
        f"data_check_{current_date}.csv"
    )
    
    # Check if file exists
    if not os.path.exists(filepath):
        print(f"Error: File not found at {filepath}")
        exit(1)
        
    results = analyze_ckd_data(filepath)
    print_results(results)