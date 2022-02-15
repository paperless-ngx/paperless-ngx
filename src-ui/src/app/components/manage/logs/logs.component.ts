import { Component, ElementRef, OnInit, AfterViewChecked, ViewChild } from '@angular/core';
import { LogService } from 'src/app/services/rest/log.service';

@Component({
  selector: 'app-logs',
  templateUrl: './logs.component.html',
  styleUrls: ['./logs.component.scss']
})
export class LogsComponent implements OnInit, AfterViewChecked {

  constructor(private logService: LogService) { }

  logs: string[] = []

  logFiles: string[] = []

  activeLog: string

  @ViewChild('logContainer') logContainer: ElementRef

  ngOnInit(): void {
    this.logService.list().subscribe(result => {
      this.logFiles = result
      if (this.logFiles.length > 0) {
        this.activeLog = this.logFiles[0]
        this.reloadLogs()
      }
    })
  }

  ngAfterViewChecked() {
    this.scrollToBottom();
  }

  reloadLogs() {
    this.logService.get(this.activeLog).subscribe(result => {
      this.logs = result
    }, error => {
      this.logs = []
    })
  }

  getLogLevel(log: string) {
    if (log.indexOf("[DEBUG]") != -1) {
      return 10
    } else if (log.indexOf("[WARNING]") != -1) {
      return 30
    } else if (log.indexOf("[ERROR]") != -1) {
      return 40
    } else if (log.indexOf("[CRITICAL]") != -1) {
      return 50
    } else {
      return 20
    }
  }

  scrollToBottom(): void {
    this.logContainer?.nativeElement.scroll({
      top: this.logContainer.nativeElement.scrollHeight,
      left: 0,
      behavior: 'auto'
    });
  }

}
