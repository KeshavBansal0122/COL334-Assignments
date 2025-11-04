#!/bin/bash
# Quick test script for Part 1

echo "=================================="
echo "Part 1: Testing Reliable UDP"
echo "=================================="

# Set parameters
SERVER_IP="127.0.0.1"
SERVER_PORT="6555"
SWS="5900"  # 5 packets of 1180 bytes

cd part1

# Clean up old received file
rm -f received_data.txt

# Start server in background
echo "Starting server..."
python3 p1_server.py $SERVER_IP $SERVER_PORT $SWS &
SERVER_PID=$!

# Give server time to start
sleep 1

# Start client
echo "Starting client..."
python3 p1_client.py $SERVER_IP $SERVER_PORT

# Wait for transfer to complete
sleep 2

# Kill server
kill $SERVER_PID 2>/dev/null

# Verify transfer
echo ""
echo "=================================="
echo "Verification:"
echo "=================================="

if [ -f "received_data.txt" ]; then
    ORIG_SIZE=$(wc -c < data.txt)
    RECV_SIZE=$(wc -c < received_data.txt)
    ORIG_MD5=$(md5sum data.txt | awk '{print $1}')
    RECV_MD5=$(md5sum received_data.txt | awk '{print $1}')
    
    echo "Original size: $ORIG_SIZE bytes"
    echo "Received size: $RECV_SIZE bytes"
    echo ""
    echo "Original MD5: $ORIG_MD5"
    echo "Received MD5: $RECV_MD5"
    echo ""
    
    if [ "$ORIG_MD5" = "$RECV_MD5" ]; then
        echo "✓ SUCCESS: File transferred correctly!"
    else
        echo "✗ FAILURE: File corruption detected!"
    fi
else
    echo "✗ FAILURE: received_data.txt not found!"
fi

cd ..
