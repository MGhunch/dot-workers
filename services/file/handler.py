"""
File Service
Files attachments to Dropbox job folders.

GO IN → DO THING → SEND COMMS → GET OUT

Steps:
1. Validate inputs
2. Look up job
3. File attachments to Workings
4. Post to Teams
5. Send confirmation
"""

from flask import jsonify

from utils import airtable, connect, file


# ===================
# MAIN HANDLER
# ===================

def process_file(data):
    """
    File attachments to a job's Dropbox folder.
    
    1. Validate inputs
    2. Look up job
    3. File attachments to Workings
    4. Post to Teams
    5. Send confirmation
    """
    job_number = data.get('jobNumber', '')
    attachment_names = data.get('attachmentNames', [])
    internet_message_id = data.get('internetMessageId', '')
    sender_email = data.get('senderEmail', '')
    sender_name = data.get('senderName', '')
    subject_line = data.get('subjectLine', '')
    
    # For .eml file
    received_datetime = data.get('receivedDateTime', '')
    recipients = data.get('allRecipients', [])
    email_content = data.get('emailContent', '')
    
    print(f"[file] === PROCESSING ===")
    print(f"[file] Job: {job_number}")
    print(f"[file] Sender: {sender_email}")
    print(f"[file] Attachments: {attachment_names}")
    
    # ===================
    # VALIDATE
    # ===================
    if not job_number:
        return jsonify({'success': False, 'error': 'No job number provided'}), 400
    
    if not attachment_names:
        return jsonify({'success': False, 'error': 'No attachments to file'}), 400
    
    # Track results for each step
    results = {
        'file': None,
        'teams': None,
        'email': None
    }
    
    try:
        # ===================
        # 1. LOOK UP JOB
        # ===================
        print(f"[file] Looking up job...")
        job_record_id, project_info, lookup_error = airtable.get_project(job_number)
        
        if lookup_error:
            print(f"[file] {lookup_error}")
            connect.send_failure(
                to_email=sender_email, route='file', error_message=lookup_error,
                sender_name=sender_name, job_number=job_number, subject_line=subject_line
            )
            return jsonify({'success': False, 'error': lookup_error, 'results': results})
        
        print(f"[file] Found: {project_info['projectName']}")
        
        team_id = project_info.get('teamId')
        channel_id = project_info.get('channelId')
        channel_url = project_info.get('channelUrl')
        
        # Extract client code from job number (e.g. "TOW 091" → "TOW")
        client_code = job_number.split(' ')[0] if ' ' in job_number else job_number[:3]
        
        # ===================
        # 2. FILE ATTACHMENTS
        # ===================
        print(f"[file] Filing {len(attachment_names)} attachments...")
        
        # Get email body for .eml file if not in payload
        email_body_for_eml = email_content
        if not email_body_for_eml and internet_message_id:
            email_body_for_eml = airtable.get_email_body(internet_message_id)
        
        file_result = file.file_to_dropbox(
            job_number=job_number,
            attachment_names=attachment_names,
            client_code=client_code,
            job_name=project_info['projectName'],
            route='file',
            project_record_id=job_record_id,
            email_content=email_body_for_eml,
            sender_name=sender_name,
            sender_email=sender_email,
            recipients=recipients,
            subject=subject_line,
            received_datetime=received_datetime
        )
        
        results['file'] = file_result
        
        if not file_result.get('success'):
            error_msg = file_result.get('error', 'Filing failed')
            print(f"[file] {error_msg}")
            connect.send_failure(
                to_email=sender_email, route='file', error_message=error_msg,
                sender_name=sender_name, job_number=job_number, subject_line=subject_line
            )
            return jsonify({'success': False, 'error': error_msg, 'results': results})
        
        files_count = file_result.get('count', len(attachment_names))
        dropbox_url = file_result.get('dropboxUrl', '')
        destination = file_result.get('destination', 'Workings')
        
        print(f"[file] Filed: {files_count} files to {destination}")
        
        # ===================
        # 3. POST TO TEAMS
        # ===================
        files_word = 'file' if files_count == 1 else 'files'
        teams_subject = "Files filed 📁"
        
        file_list = ''.join(f'<li>{f}</li>' for f in file_result.get('filesMoved', []))
        teams_body = f"Filed {files_count} {files_word}:<br><ul>{file_list}</ul>"
        
        if dropbox_url:
            teams_body += f'<a href="{dropbox_url}">View files here</a>'
        
        print(f"[file] Posting to Teams...")
        teams_result = connect.post_to_teams(
            team_id=team_id, channel_id=channel_id,
            subject=teams_subject, body=teams_body, job_number=job_number
        )
        results['teams'] = teams_result
        print(f"[file] Teams: {teams_result.get('success')}")
        
        # ===================
        # 4. SEND CONFIRMATION
        # ===================
        original_email = {
            'senderName': sender_name,
            'senderEmail': sender_email,
            'subject': subject_line,
            'receivedDateTime': received_datetime,
            'content': email_body_for_eml
        }
        
        print(f"[file] Sending confirmation...")
        email_result = connect.send_confirmation(
            to_email=sender_email, route='file', sender_name=sender_name,
            job_number=job_number, job_name=project_info['projectName'],
            subject_line=subject_line, original_email=original_email,
            files_url=dropbox_url, channel_url=channel_url, results=results
        )
        results['email'] = email_result
        print(f"[file] Email: {email_result.get('success')}")
        
        # ===================
        # DONE
        # ===================
        print(f"[file] === COMPLETE ===")
        return jsonify({
            'success': True,
            'jobNumber': job_number,
            'projectName': project_info['projectName'],
            'filesFiled': files_count,
            'destination': destination,
            'dropboxUrl': dropbox_url,
            'results': results,
            'teamsPosted': results['teams'].get('success', False) if results['teams'] else False,
            'emailSent': results['email'].get('success', False) if results['email'] else False
        })
        
    except Exception as e:
        print(f"[file] Error: {e}")
        import traceback
        traceback.print_exc()
        connect.send_failure(
            to_email=sender_email, route='file', error_message=str(e),
            sender_name=sender_name, job_number=job_number, subject_line=subject_line
        )
        return jsonify({'success': False, 'error': str(e), 'results': results}), 500
