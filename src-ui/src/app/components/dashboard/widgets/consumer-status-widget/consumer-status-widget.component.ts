import { Component, OnInit } from '@angular/core';
import { ConsumerStatusService, FileStatus } from 'src/app/services/consumer-status.service';

@Component({
  selector: 'app-consumer-status-widget',
  templateUrl: './consumer-status-widget.component.html',
  styleUrls: ['./consumer-status-widget.component.css']
})
export class ConsumerStatusWidgetComponent implements OnInit {

  constructor(private consumerStatusService: ConsumerStatusService) { }

  ngOnInit(): void {
  }

  getStatus() {
    return this.consumerStatusService.consumerStatus
  }

  isFinished(status: FileStatus) {
    return status.status == "FAILED" || status.status == "SUCCESS"
  }

  getType(status) {
    switch (status) {
      case "WORKING": return "primary"
      case "FAILED": return "danger"
      case "SUCCESS": return "success"
    }
  }

  dismiss(status: FileStatus) {
    this.consumerStatusService.dismiss(status)
  }
}
