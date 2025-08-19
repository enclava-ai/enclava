#!/bin/bash

# Simple integration test using curl
echo "🔧 Simple Module Integration Test"
echo "================================="

# Test if the API is responding
echo "Testing API endpoint..."
response=$(curl -s -w "HTTPSTATUS:%{http_code}" http://localhost:8000/api/v1/modules/)

# Extract HTTP status code
http_code=$(echo $response | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')

# Extract response body
body=$(echo $response | sed -E 's/HTTPSTATUS:[0-9]{3}$//')

if [ "$http_code" -eq 200 ]; then
    echo "✅ API responding successfully (HTTP $http_code)"
    
    # Parse JSON response using jq if available
    if command -v jq >/dev/null 2>&1; then
        echo "📊 Module Status:"
        echo "$body" | jq -r '
            "Total modules: " + (.total | tostring),
            "Initialized: " + (.initialized | tostring),
            "",
            "Module Details:",
            (.modules[] | "  🔹 " + .name + " v" + .version + 
             (if .initialized then " ✅" else " ⏳" end) +
             (if .stats then " (stats: " + (.stats | keys | length | tostring) + ")" else "" end))
        '
        
        # Test specific functionality
        echo ""
        echo "🧪 Testing Module Functionality:"
        
        # Check if we have expected modules
        cache_present=$(echo "$body" | jq -r '.modules[] | select(.name=="cache") | .name // empty')
        monitoring_present=$(echo "$body" | jq -r '.modules[] | select(.name=="monitoring") | .name // empty')
        config_present=$(echo "$body" | jq -r '.modules[] | select(.name=="config") | .name // empty')
        
        if [ "$cache_present" = "cache" ]; then
            echo "  ✅ Cache module found"
        else
            echo "  ❌ Cache module missing"
        fi
        
        if [ "$monitoring_present" = "monitoring" ]; then
            echo "  ✅ Monitoring module found"
            # Check monitoring stats
            cpu=$(echo "$body" | jq -r '.modules[] | select(.name=="monitoring") | .stats.current_cpu // "N/A"')
            memory=$(echo "$body" | jq -r '.modules[] | select(.name=="monitoring") | .stats.current_memory // "N/A"')
            echo "    📈 CPU: ${cpu}%"
            echo "    📈 Memory: ${memory}%"
        else
            echo "  ❌ Monitoring module missing"
        fi
        
        if [ "$config_present" = "config" ]; then
            echo "  ✅ Config module found"
            # Check config stats
            configs=$(echo "$body" | jq -r '.modules[] | select(.name=="config") | .stats.total_configs // "N/A"')
            watchers=$(echo "$body" | jq -r '.modules[] | select(.name=="config") | .stats.active_watchers // "N/A"')
            echo "    ⚙️  Configurations: $configs"
            echo "    👀 Active watchers: $watchers"
        else
            echo "  ❌ Config module missing"
        fi
        
        # Count total modules
        total_modules=$(echo "$body" | jq -r '.total')
        if [ "$total_modules" -ge 7 ]; then
            echo "  ✅ Expected module count: $total_modules/7+"
        else
            echo "  ❌ Insufficient modules: $total_modules/7+"
        fi
        
    else
        echo "📊 Raw JSON Response:"
        echo "$body" | python3 -m json.tool 2>/dev/null || echo "$body"
    fi
    
    echo ""
    echo "🎉 Integration test completed successfully!"
    exit 0
    
else
    echo "❌ API request failed (HTTP $http_code)"
    echo "Response: $body"
    exit 1
fi