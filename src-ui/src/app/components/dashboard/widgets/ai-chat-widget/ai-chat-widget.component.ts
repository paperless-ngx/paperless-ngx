import { Component, ViewChild, ElementRef } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { WidgetFrameComponent } from '../widget-frame/widget-frame.component';
import { CommonModule } from '@angular/common';

interface ChatMessage {
  text: string;
  fromUser: boolean;
}

@Component({
  selector: 'app-ai-chat-widget',
  templateUrl: './ai-chat-widget.component.html',
  styleUrls: ['./ai-chat-widget.component.scss'],
  imports: [
    FormsModule,
    WidgetFrameComponent,
    CommonModule
  ]
})
export class AiChatWidgetComponent {
  @ViewChild('chatContainer', { static: false }) chatContainer: ElementRef;
  messages: ChatMessage[] = [];
  currentMessage = '';
  showTypingAnimation = false;

  constructor(private http: HttpClient) { }

  sendMessage() {
    if (this.currentMessage.trim() === '') {
      return;
    }

    // Add the user's message to the chat
    this.messages.push({
      text: this.currentMessage,
      fromUser: true
    });
    // Scroll the chat container to the bottom
    setTimeout(() => {
      this.chatContainer.nativeElement.scrollTop = this.chatContainer.nativeElement.scrollHeight;
    });

    // Send the message to a chatbot API and display the response
    const apiUrl = 'http://localhost:4321/question';
    const requestBody = { question: this.currentMessage };
    const headers = {
      Authorization: 'Bearer ' + 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIzNTYzNDU2NyIsIm5hbWUiOiJKb3NjaGthIiwiaWF0IjoxNTE2MjM5MDIyfQ.iecqerProyQ4OyhjzyMtHEb869b3Vbitp_T5tkip2Z4'
    };
    this.showTypingAnimation = true; // show the typing animation
    this.http.post(apiUrl, requestBody, { headers }).subscribe((response: any) => {
      this.showTypingAnimation = false; // hide the typing animation
      // Add the chatbot's response to the chat
      this.messages.push({
        text: response.german,
        fromUser: false
      });
      // Scroll the chat container to the bottom
      setTimeout(() => {
        this.chatContainer.nativeElement.scrollTop = this.chatContainer.nativeElement.scrollHeight;
      });
    });

    // Clear the input field
    this.currentMessage = '';
  }
}