import { CommonModule } from '@angular/common'
import {
  ChangeDetectorRef,
  Component,
  ElementRef,
  OnDestroy,
  OnInit,
  ViewChild,
  inject,
} from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgbNavModule } from '@ng-bootstrap/ng-bootstrap'
import { Subject, debounceTime, filter, takeUntil, timer } from 'rxjs'
import { LogService } from 'src/app/services/rest/log.service'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'

@Component({
  selector: 'pngx-logs',
  templateUrl: './logs.component.html',
  styleUrls: ['./logs.component.scss'],
  imports: [
    PageHeaderComponent,
    NgbNavModule,
    CommonModule,
    FormsModule,
    ReactiveFormsModule,
  ],
})
export class LogsComponent
  extends LoadingComponentWithPermissions
  implements OnInit, OnDestroy
{
  private logService = inject(LogService)
  private changedetectorRef = inject(ChangeDetectorRef)

  public logs: Array<{ message: string; level: number }> = []

  public logFiles: string[] = []

  public activeLog: string

  public autoRefreshEnabled: boolean = true

  public limit: number = 5000

  public showJumpToBottom = false

  private readonly limitChange$ = new Subject<number>()

  @ViewChild('logContainer') logContainer: ElementRef<HTMLElement>

  ngOnInit(): void {
    this.limitChange$
      .pipe(debounceTime(300), takeUntil(this.unsubscribeNotifier))
      .subscribe(() => this.reloadLogs())

    this.logService
      .list()
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((result) => {
        this.logFiles = result
        this.loading = false
        if (this.logFiles.length > 0) {
          this.activeLog = this.logFiles[0]
          this.reloadLogs()
        }
        timer(5000, 5000)
          .pipe(
            filter(() => this.autoRefreshEnabled),
            takeUntil(this.unsubscribeNotifier)
          )
          .subscribe(() => {
            this.reloadLogs()
          })
      })
  }

  ngOnDestroy(): void {
    super.ngOnDestroy()
  }

  onLimitChange(limit: number): void {
    this.limitChange$.next(limit)
  }

  reloadLogs() {
    this.loading = true
    const shouldStickToBottom = this.isNearBottom()
    this.logService
      .get(this.activeLog, this.limit)
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: (result) => {
          this.loading = false
          const parsed = this.parseLogsWithLevel(result)
          const hasChanges =
            parsed.length !== this.logs.length ||
            parsed.some((log, idx) => {
              const current = this.logs[idx]
              return (
                !current ||
                current.message !== log.message ||
                current.level !== log.level
              )
            })
          if (hasChanges) {
            this.logs = parsed
            if (shouldStickToBottom) {
              this.scrollToBottom()
            }
            this.showJumpToBottom = !shouldStickToBottom
          }
        },
        error: () => {
          this.logs = []
          this.loading = false
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

  private parseLogsWithLevel(
    logs: string[]
  ): Array<{ message: string; level: number }> {
    return logs.map((log) => ({
      message: log,
      level: this.getLogLevel(log),
    }))
  }

  scrollToBottom(): void {
    const viewport = this.logContainer?.nativeElement
    if (!viewport) {
      return
    }
    this.changedetectorRef.detectChanges()
    viewport.scrollTop = viewport.scrollHeight
    this.showJumpToBottom = false
  }

  private isNearBottom(): boolean {
    if (!this.logContainer?.nativeElement) return true
    const distanceFromBottom =
      this.logContainer.nativeElement.scrollHeight -
      this.logContainer.nativeElement.scrollTop -
      this.logContainer.nativeElement.clientHeight
    return distanceFromBottom <= 40
  }

  onScroll(): void {
    this.showJumpToBottom = !this.isNearBottom()
  }
}
