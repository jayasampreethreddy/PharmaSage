# PharmaSage - Molecular Visualization & Analysis Platform

A modern Flask web application for 3D molecular visualization and drug comparison using clinical drug data.

## Features

🔹 **Molecule 3D Visualizer**
- Interactive 3D molecular structure rendering using 3Dmol.js
- Dropdown selection of drugs from the clinical dataset
- Search functionality for drug names or SMILES strings
- Display of comprehensive molecular properties

🔹 **Molecule Comparator**
- Side-by-side comparison of two drugs
- 3D structure visualization for both molecules
- Property comparison with highlighting of differences
- Automated textual summary of key differences

🔹 **Modern UI Design**
- Beautiful pharmaceutical dashboard interface
- Bootstrap 5 styling with custom CSS
- Responsive design for all devices
- Interactive cards and smooth animations

## Data Source

The application uses the `data/cleaned_clinical_drugs_dataset.csv` file containing:
- Drug identifiers and names
- SMILES molecular representations
- Physical properties (logP, logD, PSA, etc.)
- Biological data (IC50, pIC50, targets, mechanisms)
- Toxicity alerts and development phases

## Installation & Setup

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Verify Data File**
   Ensure `data/cleaned_clinical_drugs_dataset.csv` exists in the project directory.

3. **Run the Application**
   ```bash
   python app.py
   ```

4. **Access the Application**
   Open your browser and navigate to: `http://localhost:5000`

## File Structure

```
pharmasage/
├── app.py                          # Main Flask application
├── requirements.txt                # Python dependencies
├── data/
│   └── cleaned_clinical_drugs_dataset.csv  # Drug dataset
├── templates/
│   └── index.html                 # Main application template
└── static/
    └── js/
        └── viewer.js              # JavaScript for 3D visualization
```

## API Endpoints

- `GET /` - Main application page
- `GET /api/drugs` - Get list of all available drugs
- `GET /api/drug/<drug_name>` - Get drug information by name
- `GET /api/search_drug?query=<search_term>` - Search drugs by name or SMILES
- `GET /api/compare_drugs?drug1=<name>&drug2=<name>` - Compare two drugs

## Usage

### Molecule Visualizer
1. Select a drug from the dropdown or enter a drug name/SMILES
2. Click "Load Molecule" to render the 3D structure
3. View molecular properties in the side panel
4. Interact with the 3D viewer (rotate, zoom, pan)

### Molecule Comparator
1. Select two different drugs from the dropdowns
2. Click "Compare Drugs" to generate comparison
3. View side-by-side 3D structures
4. Compare properties with highlighted differences
5. Read the automated comparison summary

## Technical Details

- **Backend**: Flask with pandas for data handling
- **Frontend**: Bootstrap 5 + custom CSS for modern UI
- **3D Visualization**: 3Dmol.js for molecular rendering
- **Data Processing**: Pandas for CSV handling and data manipulation
- **Responsive Design**: Mobile-friendly interface

## Features in Detail

### Molecular Properties Displayed
- **Physical Properties**: LogP, LogD, PSA (Polar Surface Area)
- **Biological Data**: IC50, pIC50, Drug Likeness
- **Target Information**: Protein targets, organisms, mechanisms
- **Safety Data**: Toxicity alerts, development phases
- **Identifiers**: Drug IDs, MeSH headings, EFO terms

### Comparison Features
- **Toxicity Comparison**: Highlight differences in safety profiles
- **Binding Affinity**: Compare pIC50 values and differences
- **Lipophilicity**: Compare LogP values for drug-like properties
- **Target Analysis**: Identify same vs different protein targets
- **Development Status**: Compare clinical development phases

## Browser Compatibility

- Chrome/Chromium (recommended)
- Firefox
- Safari
- Edge

## Troubleshooting

1. **Data Loading Issues**
   - Verify the CSV file exists and is readable
   - Check file permissions
   - Ensure pandas is installed correctly

2. **3D Visualization Issues**
   - Ensure JavaScript is enabled
   - Check browser console for errors
   - Try refreshing the page

3. **Performance Issues**
   - Large datasets may take time to load initially
   - Consider reducing dataset size for testing

## Development

To modify the application:

1. **Add New Properties**: Update the `displayProperties()` function in `viewer.js`
2. **Modify Styling**: Edit CSS in `templates/index.html`
3. **Add New Endpoints**: Extend `app.py` with new Flask routes
4. **Enhance Comparison**: Modify `generate_comparison_summary()` function

## License

This project is part of the PharmaSage platform for pharmaceutical research and development. 