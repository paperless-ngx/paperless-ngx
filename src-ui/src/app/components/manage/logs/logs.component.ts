import { Component, OnInit } from '@angular/core';
import { Title } from '@angular/platform-browser';
import { kMaxLength } from 'buffer';
import { LOG_LEVELS, LOG_LEVEL_INFO, PaperlessLog } from 'src/app/data/paperless-log';
import { LogService } from 'src/app/services/rest/log.service';
import { environment } from 'src/environments/environment';

@Component({
  selector: 'app-logs',
  templateUrl: './logs.component.html',
  styleUrls: ['./logs.component.scss']
})
export class LogsComponent implements OnInit {

  constructor(private logService: LogService, private titleService: Title) { }

  logs: PaperlessLog[] = []
  level: number = LOG_LEVEL_INFO

  ngOnInit(): void {
    this.reload()
    this.titleService.setTitle(`Logs - ${environment.appTitle}`)
  }

  reload() {
    this.logService.list(1, 50, 'created', 'des', {'level__gte': this.level}).subscribe(result => this.logs = result.results)
  }

  getLevelText(level: number) {
    return LOG_LEVELS.find(l => l.id == level)?.name
  }

  onScroll() {
    let lastCreated = null
    if (this.logs.length > 0) {
      lastCreated = new Date(this.logs[this.logs.length-1].created).toISOString()
    }
    this.logService.list(1, 25, 'created', 'des', {'created__lt': lastCreated, 'level__gte': this.level}).subscribe(result => {
      this.logs.push(...result.results)
    })
  }

  getLevels() {
    return LOG_LEVELS
  }

  setLevel(id) {
    this.level = id
    this.reload()
  }

}
