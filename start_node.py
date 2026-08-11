#!/usr/bin/env python3
"""
MoonBite Node Starter - Enables mining and blockchain synchronization
Runs the full node with RPC server for wallet and mining operations
"""
import sys
import logging
from full_node import Node

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    """Start the MoonBite full node"""
    try:
        logger.info("🌙 MoonBite Node Starting...")
        logger.info("Initializing blockchain node...")

        # Create and run full node
        node = Node("mining-node", coinbase_maturity=0)

        logger.info(f"✅ Node initialized - Height: {node.chain.height}")
        logger.info("📡 RPC Server ready for connections")
        logger.info("⛏️  Ready for mining")

        # Keep node running
        import time
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("🛑 Node shutdown signal received")
            sys.exit(0)

    except Exception as e:
        logger.error(f"❌ Node startup failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()
