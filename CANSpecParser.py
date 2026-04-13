import pandas as pd
import re
import json
import os
from collections import defaultdict

class CANSpecParser:
    def __init__(self, excel_file):
        self.specs = {}
        self.node_id = 8
        # Manual mapping from your logs
        self.can_id_mapping = {
            0x208: 'PDO1_RX',
            0x308: 'PDO2_RX',
            0x188: 'PDO1_TX',
            0x288: 'PDO2_TX',
            0x388: 'PDO3_TX',
            0x88: 'EMERG',
            0x708: 'HEART_BEAT',
            0x709: 'HEART_BEAT_uSupervisor',
            0x89: 'EMERG_uSupervisor',
        }
        
        # Signal definitions based on PdoMap(CanOpen) sheet
        self.signal_definitions = {
            'PDO1_RX': {
                0: {'name': 'Target Speed', 'bytes': 2, 'scale': 0.1, 'unit': 'Hz'},
                2: {'name': 'Control Word', 'bytes': 2, 'format': 'bitfield'},
                4: {'name': 'Pedal Brake', 'bytes': 1, 'scale': 1, 'unit': '0-255'},
                5: {'name': 'DC Pump', 'bytes': 1, 'scale': 1, 'unit': '0-255'},
                6: {'name': 'EVP Target', 'bytes': 1, 'scale': 1, 'unit': '0-255'},
                7: {'name': 'EVP2 Target', 'bytes': 1, 'scale': 1, 'unit': '0-255'},
            },
            'PDO2_RX': {
                0: {'name': 'Max Torque Motoring', 'bytes': 1, 'scale': 1, 'unit': '%'},
                1: {'name': 'Max Torque Braking', 'bytes': 1, 'scale': 1, 'unit': '%'},
                2: {'name': 'Control Word 2', 'bytes': 2, 'format': 'bitfield'},
                4: {'name': 'Steering Angle', 'bytes': 2, 'scale': 1, 'unit': 'degrees', 'signed': True},
                6: {'name': 'Acceleration', 'bytes': 1, 'scale': 0.1, 'unit': 's'},
                7: {'name': 'Deceleration', 'bytes': 1, 'scale': 0.1, 'unit': 's'},
            },
            'PDO1_TX': {
                0: {'name': 'Actual Speed', 'bytes': 2, 'scale': 0.1, 'unit': 'Hz', 'signed': True},
                2: {'name': 'Status Word', 'bytes': 2, 'format': 'bitfield'},
                4: {'name': 'Status Byte', 'bytes': 1, 'format': 'bitfield'},
                5: {'name': 'Analog Input 1', 'bytes': 1, 'scale': 1, 'unit': '0-255'},
                6: {'name': 'Analog Input 2', 'bytes': 1, 'scale': 1, 'unit': '0-255'},
                7: {'name': 'Actual Current', 'bytes': 1, 'scale': 1, 'unit': 'A*nominal/200'},
            },
        }
        
        self.control_word_bits = {
            0: 'Enable Power Bridge',
            1: 'Main Contactor (NMC)',
            2: 'Electric Brake (NEB)',
            3: 'Forward Request',
            4: 'Reverse Request',
            5: 'Output SAUX1',
            6: 'Output SAUX2',
            7: 'Output SAUX3',
            8: 'Output SAUX4',
            9: 'Output SAUX5',
            10: 'Horn/SAUX6',
            11: 'MC Generic Purpose',
            12: 'AGV Request',
            13: 'Reset STO/SS1',
            14: 'Free',
            15: 'Toggle Bit',
        }
        
        self.load_all_sheets(excel_file)
    
    def load_all_sheets(self, excel_file):
        try:
            df = pd.read_excel(excel_file, sheet_name='PdoMap(CanOpen)')
            self.parse_signal_table(df)
        except Exception as e:
            print(f"Could not load sheet: {e}")
    
    def parse_signal_table(self, df):
        """Parse the signal table from Excel"""
        current_pdo = None
        for idx, row in df.iterrows():
            if len(row) > 0 and pd.notna(row.iloc[0]):
                cell_str = str(row.iloc[0]).strip()
                # Check if this is a PDO header
                if 'PDO' in cell_str and ('RX' in cell_str or 'TX' in cell_str):
                    current_pdo = cell_str.upper().replace('_', '')
                    if current_pdo in self.signal_definitions:
                        print(f"Found PDO: {current_pdo}")
    
    def decode_can_message(self, can_id, data_hex):
        """Decode CAN message based on ID"""
        # Convert hex string to bytes
        try:
            data_bytes = bytes.fromhex(data_hex)
        except:
            return {'error': f'Invalid hex: {data_hex}'}
        
        # Get PDO name from mapping
        pdo_name = self.can_id_mapping.get(can_id, 'Unknown')
        
        decoded = {
            'can_id': hex(can_id),
            'pdo_name': pdo_name,
            'data_hex': data_hex,
            'signals': {}
        }
        
        if pdo_name == 'Unknown':
            return decoded
        
        # Decode based on PDO type
        if pdo_name in self.signal_definitions:
            signals = self.signal_definitions[pdo_name]
            
            for byte_pos, signal_info in signals.items():
                if byte_pos + signal_info['bytes'] <= len(data_bytes):
                    # Extract value (little-endian)
                    value = 0
                    for i in range(signal_info['bytes']):
                        value |= (data_bytes[byte_pos + i] << (8 * i))
                    
                    # Handle signed values
                    if signal_info.get('signed', False) and value & (1 << (8 * signal_info['bytes'] - 1)):
                        value = value - (1 << (8 * signal_info['bytes']))
                    
                    # Apply scale
                    scaled_value = value * signal_info.get('scale', 1)
                    
                    decoded['signals'][signal_info['name']] = {
                        'raw': value,
                        'value': scaled_value,
                        'unit': signal_info.get('unit', ''),
                        'bytes': signal_info['bytes']
                    }
                    
                    # Decode bitfields for Control Word
                    if signal_info.get('format') == 'bitfield' and signal_info['name'] == 'Control Word':
                        bits = {}
                        for bit_pos, bit_name in self.control_word_bits.items():
                            bits[bit_name] = (value >> bit_pos) & 1
                        decoded['signals'][signal_info['name']]['bits'] = bits
        
        return decoded

class CANLogAnalyzer:
    def __init__(self, parser):
        self.parser = parser
        self.messages = []
        self.log_sources = {}
    
    def parse_log_file(self, log_file_path, source_name=None):
        """Parse a CAN log file"""
        if not os.path.exists(log_file_path):
            print(f"File not found: {log_file_path}")
            return []
        
        messages = []
        source = source_name or os.path.basename(log_file_path)
        
        with open(log_file_path, 'r') as f:
            for line in f:
                line = line.strip()
                # Pattern: timestamp can_id#data
                match = re.search(r'(\d+)\s+([0-9A-Fa-f]+)#([0-9A-Fa-f]+)', line)
                if match:
                    timestamp = int(match.group(1))
                    can_id = int(match.group(2), 16)
                    data = match.group(3)
                    
                    decoded = self.parser.decode_can_message(can_id, data)
                    decoded['timestamp'] = timestamp
                    decoded['source'] = source
                    messages.append(decoded)
        
        print(f"Parsed {len(messages)} messages from {source}")
        self.messages.extend(messages)
        self.log_sources[source] = len(messages)
        return messages
    
    def analyze_communication(self):
        """Analyze communication patterns"""
        print("\n" + "="*60)
        print("COMMUNICATION ANALYSIS")
        print("="*60)
        
        print(f"\nTotal messages: {len(self.messages)}")
        
        # Count by PDO type
        pdo_counts = defaultdict(int)
        for msg in self.messages:
            pdo_counts[msg.get('pdo_name', 'Unknown')] += 1
        
        print("\nMessage breakdown:")
        for pdo, count in sorted(pdo_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {pdo}: {count} ({count/len(self.messages)*100:.1f}%)")
        
        # Analyze PDO1_RX commands
        pdo1_rx_msgs = [m for m in self.messages if m.get('pdo_name') == 'PDO1_RX']
        if pdo1_rx_msgs:
            print(f"\n{'='*60}")
            print("PDO1_RX ANALYSIS (Master Commands)")
            print('='*60)
            
            # Speed commands
            speeds = []
            for msg in pdo1_rx_msgs[:100]:  # Sample first 100
                if 'Target Speed' in msg.get('signals', {}):
                    speed = msg['signals']['Target Speed']['value']
                    speeds.append(speed)
            
            if speeds:
                print(f"Target Speed range: {min(speeds):.1f} to {max(speeds):.1f} Hz")
            
            # Control word analysis
            toggle_bits = []
            enable_bits = []
            for msg in pdo1_rx_msgs[:100]:
                if 'Control Word' in msg.get('signals', {}):
                    bits = msg['signals']['Control Word'].get('bits', {})
                    toggle_bits.append(bits.get('Toggle Bit', 0))
                    enable_bits.append(bits.get('Enable Power Bridge', 0))
            
            if toggle_bits:
                toggle_changes = sum(1 for i in range(1, len(toggle_bits)) if toggle_bits[i] != toggle_bits[i-1])
                print(f"Toggle bit toggling correctly: {toggle_changes}/{len(toggle_bits)-1} changes")
                print(f"Power bridge enabled: {sum(enable_bits)}/{len(enable_bits)} times")
        
        # Analyze PDO1_TX responses
        pdo1_tx_msgs = [m for m in self.messages if m.get('pdo_name') == 'PDO1_TX']
        if pdo1_tx_msgs:
            print(f"\n{'='*60}")
            print("PDO1_TX ANALYSIS (Inverter Responses)")
            print('='*60)
            
            speeds = []
            for msg in pdo1_tx_msgs[:100]:
                if 'Actual Speed' in msg.get('signals', {}):
                    speed = msg['signals']['Actual Speed']['value']
                    speeds.append(speed)
            
            if speeds:
                print(f"Actual Speed range: {min(speeds):.1f} to {max(speeds):.1f} Hz")
    
    def detect_anomalies(self):
        """Detect real anomalies"""
        anomalies = []
        
        # Check toggle bit for same PDO
        toggle_history = defaultdict(list)
        
        for msg in self.messages:
            pdo = msg.get('pdo_name')
            if pdo != 'Unknown' and 'Control Word' in msg.get('signals', {}):
                bits = msg['signals']['Control Word'].get('bits', {})
                if 'Toggle Bit' in bits:
                    toggle = bits['Toggle Bit']
                    toggle_history[pdo].append({
                        'timestamp': msg['timestamp'],
                        'toggle': toggle,
                        'source': msg.get('source')
                    })
        
        # Find toggle bit errors
        for pdo, history in toggle_history.items():
            for i in range(1, len(history)):
                if history[i]['toggle'] == history[i-1]['toggle']:
                    anomalies.append({
                        'type': 'Toggle Bit Stuck',
                        'pdo': pdo,
                        'timestamp': history[i]['timestamp'],
                        'source': history[i]['source'],
                        'expected': 1 - history[i-1]['toggle'],
                        'actual': history[i]['toggle']
                    })
        
        print(f"\n{'='*60}")
        print("ANOMALY DETECTION")
        print('='*60)
        print(f"Found {len(anomalies)} real anomalies")
        
        if anomalies:
            print("\nSample anomalies:")
            for anomaly in anomalies[:10]:
                print(f"  {anomaly}")
        
        return anomalies
    
    def export_for_ai(self):
        """Export data for AI/ML analysis"""
        # Create time-series data
        time_series = []
        for msg in self.messages[:10000]:  # Sample first 10k for AI
            if msg.get('pdo_name') in ['PDO1_RX', 'PDO1_TX']:
                entry = {
                    'timestamp': msg['timestamp'],
                    'pdo': msg['pdo_name'],
                    'source': msg.get('source')
                }
                
                # Add signals
                for sig_name, sig_data in msg.get('signals', {}).items():
                    if 'speed' in sig_name.lower():
                        entry['speed_hz'] = sig_data['value']
                    elif 'brake' in sig_name.lower():
                        entry['brake'] = sig_data['value']
                    elif 'Control Word' in sig_name:
                        entry['toggle_bit'] = sig_data.get('bits', {}).get('Toggle Bit', 0)
                        entry['power_enabled'] = sig_data.get('bits', {}).get('Enable Power Bridge', 0)
                
                time_series.append(entry)
        
        # Save for AI training
        with open('can_timeseries_ai.json', 'w') as f:
            json.dump(time_series, f, indent=2)
        
        print(f"\nExported {len(time_series)} records for AI analysis")
        return time_series

# Main execution
if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    excel_path = os.path.join(script_dir, 'PdoMap.xlsx')
    
    print("Loading CAN specification...")
    parser = CANSpecParser(excel_path)
    
    analyzer = CANLogAnalyzer(parser)
    
    # Parse all three logs
    log_files = ['can_073.log', 'can_074.log', 'can_075.log']
    
    for log_file in log_files:
        log_path = os.path.join(script_dir, log_file)
        if os.path.exists(log_path):
            analyzer.parse_log_file(log_path, log_file.replace('.log', ''))
    
    if analyzer.messages:
        # Analyze communication
        analyzer.analyze_communication()
        
        # Detect anomalies
        anomalies = analyzer.detect_anomalies()
        
        # Export for AI
        ts_data = analyzer.export_for_ai()
        
        # Save full decoded messages
        with open('decoded_messages.json', 'w') as f:
            json.dump(analyzer.messages[:5000], f, indent=2, default=str)
        
        print(f"\n{'='*60}")
        print("SUMMARY")
        print('='*60)
        print(f"✓ Processed {len(analyzer.messages)} messages")
        print(f"✓ Found {len(anomalies)} toggle bit anomalies")
        print(f"✓ Exported {len(ts_data)} records for AI training")
        print("\nFiles created:")
        print("  - decoded_messages.json (first 5000 messages)")
        print("  - can_timeseries_ai.json (for AI/ML analysis)")