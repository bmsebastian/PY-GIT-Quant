#!/usr/bin/env python3
import os, sys, platform, subprocess, shutil, argparse

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--init', action='store_true', help='Create .env with sane defaults')
    args = p.parse_args()
    if args.init:
        if not os.path.exists('.env'):
            with open('.env','w') as f:
                f.write(
                    "DRY_RUN=1\n"
                    "IB_HOST=127.0.0.1\n"
                    "IB_PORT=7497\n"
                    "IB_CLIENT_ID=7\n"
                    "IB_MKT_DATA_TYPE=1\n"
                    "DATA_DIR=./data\n"
                    "UNIVERSE=ES,NQ,SPY\n"
                    "PER_SYMBOL_NOTIONAL_CAP=50000\n"
                    "MAX_POSITION_PER_SYMBOL=5\n"
                    "MAX_ORDERS_PER_DAY_PER_SYMBOL=50\n"
                    "ENABLE_RTH_GUARD=1\n"
                    "ENABLE_CALENDAR=0\n"
                    "KILL_SWITCH_FILE=./KILL_SWITCH.ON\n"
                )
            print("Created default .env")
        else:
            print(".env already exists")
    else:
        p.print_help()

if __name__ == '__main__':
    main()
