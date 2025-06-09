import configparser
from pathlib import Path
import itertools

def generate_test_configs(output_dir):
    """Generate test configuration files with different parameter combinations."""
    # Ensure output directory exists
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Define parameter combinations to test
    test_params = {
        'passes': [1, 200, 400],
        'interval': [1, 5, 10],
        'delay': [1, 10, 20],
        'sgn_level': [-100, -30, 0, 100],
        'booleans': [True, False]  # For all boolean fields
    }

    # Generate combinations
    for p, i, d, s, b in itertools.product(
        test_params['passes'],
        test_params['interval'],
        test_params['delay'],
        test_params['sgn_level'],
        test_params['booleans']
    ):
        config = configparser.ConfigParser()

        # Scanning section
        config['Scanning'] = {
            'passes': str(p),
            'aggr_scan': str(b).lower(),
            'auto_bookmark': str(not b).lower(),  # Alternate boolean value
            'range_min': '24,000',
            'range_max': '1800,000',
            'interval': str(i),
            'delay': str(d),
            'record': str(b).lower(),
            'sgn_level': str(s),
            'wait': str(not b).lower()
        }

        # Main section
        config['Main'] = {
            'log_filename': 'none',
            'save_exit': str(b).lower(),
            'always_on_top': str(not b).lower(),
            'log': str(b).lower(),
            'bookmark_filename': './test/test_files/test-bookmarks.csv'
        }

        # Rig URI section
        config['Rig URI'] = {
            'hostname1': '127.0.0.1',
            'hostname2': '127.0.0.1',
            'port1': '7356',
            'port2': '7357'
        }

        # Monitor section (empty as in sample)
        config['Monitor'] = {}

        # Generate unique filename based on parameters
        filename = f'test-config_{p}_{i}_{d}_{s}.ini'
        file_path = output_path / filename

        # Write config to file
        with open(file_path, 'w') as configfile:
            config.write(configfile)

if __name__ == '__main__':
    # Generate test files in a test_configs directory
    generate_test_configs('./test_configs')
