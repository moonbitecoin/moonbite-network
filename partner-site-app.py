"""
MoonBite Partner Portal Flask Application
Deploy to: /opt/partner-site/app.py
"""

from flask import Flask, render_template, request, jsonify
import os
from datetime import datetime

app = Flask(__name__)

# Partner data (in production, use database)
PARTNERS = [
    {
        'id': 1,
        'name': 'MoonBite Exchange',
        'description': 'Leading cryptocurrency exchange',
        'category': 'Exchange',
        'status': 'active',
        'commission': '5%'
    },
    {
        'id': 2,
        'name': 'Moon Wallet Pro',
        'description': 'Premium wallet provider',
        'category': 'Wallet',
        'status': 'active',
        'commission': '3%'
    },
    {
        'id': 3,
        'name': 'Lunar Mining Pool',
        'description': 'Community mining pool',
        'category': 'Mining',
        'status': 'active',
        'commission': '2%'
    }
]

@app.route('/')
def home():
    """Partner portal homepage"""
    return render_template('index.html', partner_count=len(PARTNERS))

@app.route('/partners')
def partners_list():
    """List all partners"""
    return render_template('partners.html', partners=PARTNERS)

@app.route('/api/partners')
def api_partners():
    """API endpoint for partner data"""
    return jsonify({
        'success': True,
        'data': PARTNERS,
        'count': len(PARTNERS)
    })

@app.route('/api/partner/<int:partner_id>')
def api_partner_detail(partner_id):
    """Get single partner details"""
    partner = next((p for p in PARTNERS if p['id'] == partner_id), None)
    if not partner:
        return jsonify({'error': 'Partner not found'}), 404
    return jsonify({'success': True, 'data': partner})

@app.route('/dashboard')
def dashboard():
    """Partner dashboard (mock data)"""
    dashboard_data = {
        'total_referrals': 1234,
        'active_partners': len(PARTNERS),
        'monthly_commission': 5420.50,
        'growth': 23.5
    }
    return render_template('dashboard.html', data=dashboard_data)

@app.route('/apply', methods=['GET', 'POST'])
def apply_partner():
    """Apply to become a partner"""
    if request.method == 'GET':
        return render_template('apply.html')

    if request.method == 'POST':
        data = request.get_json()

        # Validate required fields
        required = ['company', 'email', 'category', 'website']
        if not all(field in data for field in required):
            return jsonify({'error': 'Missing required fields'}), 400

        # Process application (in production: save to database)
        application = {
            'company': data.get('company'),
            'email': data.get('email'),
            'category': data.get('category'),
            'website': data.get('website'),
            'message': data.get('message', ''),
            'submitted_at': datetime.now().isoformat()
        }

        # TODO: Save to database
        # TODO: Send confirmation email

        return jsonify({
            'success': True,
            'message': 'Application received! We will review it shortly.',
            'reference_id': f"APP-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        })

@app.route('/resources')
def resources():
    """Partner resources and documentation"""
    resources_data = {
        'api_docs': 'https://docs.moonbite.org/api',
        'sdk': 'https://github.com/moonbite/sdk',
        'support': 'support@moonbite.org',
        'community': 'https://community.moonbite.org'
    }
    return render_template('resources.html', resources=resources_data)

@app.route('/faq')
def faq():
    """FAQ page"""
    faqs = [
        {
            'question': 'What commission do partners earn?',
            'answer': 'Commission rates vary from 2-5% depending on partnership tier.'
        },
        {
            'question': 'How do I get paid?',
            'answer': 'Payouts are processed monthly via direct transfer.'
        },
        {
            'question': 'What support is available?',
            'answer': 'Dedicated partner support team available 24/7 via email and chat.'
        },
        {
            'question': 'Can I integrate with my platform?',
            'answer': 'Yes! We provide comprehensive APIs and SDKs for integration.'
        }
    ]
    return render_template('faq.html', faqs=faqs)

@app.route('/contact', methods=['POST'])
def contact():
    """Contact form submission"""
    data = request.get_json()

    # Validate
    if not data.get('email') or not data.get('message'):
        return jsonify({'error': 'Email and message required'}), 400

    # TODO: Send email to support

    return jsonify({
        'success': True,
        'message': 'Message received. We will get back to you soon.'
    })

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(error):
    """Handle 500 errors"""
    return render_template('500.html'), 500

if __name__ == '__main__':
    # Development only
    app.run(host='127.0.0.1', port=8051, debug=False)
