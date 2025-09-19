import * as vscode from 'vscode';
import fetch from 'node-fetch';
import EventSource from 'eventsource';

export function activate(context: vscode.ExtensionContext) {

	let disposable = vscode.commands.registerCommand('hive-ide.chat', () => {
		const panel = vscode.window.createWebviewPanel(
			'hiveChat',
			'Hive Chat',
			vscode.ViewColumn.One,
			{
				enableScripts: true
			}
		);

		panel.webview.html = getWebviewContent();

		panel.webview.onDidReceiveMessage(
			async message => {
				switch (message.command) {
					case 'sendMessage':
						const res = await fetch('http://localhost:3000/api/hive/chat', {
							method: 'POST',
							headers: {
								'Content-Type': 'application/json',
							},
							body: JSON.stringify({ message: message.text }),
						});

						if (!res.ok) {
							panel.webview.postMessage({ text: 'Error: Failed to send message' });
							return;
						}

						const { jobId } = await res.json();

						const eventSource = new EventSource(`http://localhost:3000/api/hive/jobs/${jobId}/stream`);

						eventSource.onmessage = (event) => {
							const data = JSON.parse(event.data);
							panel.webview.postMessage({ text: data.message });
						};

						eventSource.onerror = (error) => {
							console.error(error);
							eventSource.close();
						};

						return;
				}
			},
			undefined,
			context.subscriptions
		);
	});

	context.subscriptions.push(disposable);
}

function getWebviewContent() {
	return `<!DOCTYPE html>
	<html lang="en">
	<head>
		<meta charset="UTF-8">
		<meta name="viewport" content="width=device-width, initial-scale=1.0">
		<title>Hive Chat</title>
	</head>
	<body>
		<h1>Hive Chat</h1>
		<div id="chat-messages"></div>
		<input id="chat-input" type="text" />
		<button id="send-button">Send</button>

		<script>
			const vscode = acquireVsCodeApi();
			const chatMessages = document.getElementById('chat-messages');
			const chatInput = document.getElementById('chat-input');
			const sendButton = document.getElementById('send-button');

			sendButton.addEventListener('click', () => {
				const message = chatInput.value;
				chatInput.value = '';
				vscode.postMessage({
					command: 'sendMessage',
					text: message
				});
			});

			window.addEventListener('message', event => {
				const message = event.data; // The JSON data our extension sent
				const messageElement = document.createElement('div');
				messageElement.textContent = message.text;
				chatMessages.appendChild(messageElement);
			});
		</script>
	</body>
	</html>`;
}

export function deactivate() {}
