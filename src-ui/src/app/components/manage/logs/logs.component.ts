import { Component, OnInit } from '@angular/core';
import { kMaxLength } from 'buffer';
import { LOG_LEVELS, PaperlessLog } from 'src/app/data/paperless-log';
import { LogService } from 'src/app/services/rest/log.service';

@Component({
  selector: 'app-logs',
  templateUrl: './logs.component.html',
  styleUrls: ['./logs.component.css']
})
export class LogsComponent implements OnInit {

  constructor(private logService: LogService) { }

  logs: PaperlessLog[] = []

  ngOnInit(): void {
    this.logService.list(1, 50).subscribe(result => this.logs = result.results)
  }

  getLevelText(level: number) {
    return LOG_LEVELS.find(l => l.id == level)?.name
  }

  onScroll() {
    let lastCreated = null
    if (this.logs.length > 0) {
      lastCreated = this.logs[this.logs.length-1].created
    }
    this.logService.list(1, 25, null, {'created__lt': lastCreated}).subscribe(result => {
      this.logs.push(...result.results)
    })
  }

}
