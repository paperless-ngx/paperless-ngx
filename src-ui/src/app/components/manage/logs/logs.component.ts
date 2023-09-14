import {
  Component,
  ElementRef,
  OnInit,
  AfterViewChecked,
  ViewChild,
  OnDestroy,
} from '@angular/core'
import { Subject, takeUntil } from 'rxjs'
import { LogService } from 'src/app/services/rest/log.service'

@Component({
  selector: 'pngx-logs',
  templateUrl: './logs.component.html',
  styleUrls: ['./logs.component.scss'],
})
export class LogsComponent implements OnInit, AfterViewChecked, OnDestroy {
  constructor(private logService: LogService) {}

  public logs: string[] = []

  public logFiles: string[] = []

  public activeLog: string

  private unsubscribeNotifier: Subject<any> = new Subject()

  public isLoading: boolean = false

  @ViewChild('logContainer') logContainer: ElementRef

  ngOnInit(): void {
    this.isLoading = true
    this.logService
      .list()
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((result) => {
        this.logFiles = result
        this.isLoading = false
        if (this.logFiles.length > 0) {
          this.activeLog = this.logFiles[0]
          this.reloadLogs()
        }
      })
  }

  ngAfterViewChecked() {
    this.scrollToBottom()
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next(true)
    this.unsubscribeNotifier.complete()
  }

  reloadLogs() {
    this.isLoading = true
    this.logService
      .get(this.activeLog)
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: (result) => {
          this.logs = result
          this.isLoading = false
        },
        error: () => {
          this.logs = []
          this.isLoading = false
        },
      })
  }

  getLogLevel(log: string) {
    if (log.indexOf('[DEBUG]') != -1) {
      return 10
    } else if (log.indexOf('[WARNING]') != -1) {
      return 30
    } else if (log.indexOf('[ERROR]') != -1) {
      return 40
    } else if (log.indexOf('[CRITICAL]') != -1) {
      return 50
    } else {
      return 20
    }
  }

  scrollToBottom(): void {
    this.logContainer?.nativeElement.scroll({
      top: this.logContainer.nativeElement.scrollHeight,
      left: 0,
      behavior: 'auto',
    })
  }
}
