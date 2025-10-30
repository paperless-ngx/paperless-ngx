import {
  CdkVirtualScrollViewport,
  ScrollingModule,
} from '@angular/cdk/scrolling'
import { CommonModule } from '@angular/common'
import {
  AfterViewInit,
  ChangeDetectorRef,
  Component,
  OnDestroy,
  OnInit,
  ViewChild,
  inject,
} from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgbNavModule } from '@ng-bootstrap/ng-bootstrap'
import { filter, takeUntil, timer } from 'rxjs'
import { LogService } from 'src/app/services/rest/log.service'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'

@Component({
  selector: 'pngx-logs',
  templateUrl: './logs.component.html',
  styleUrls: ['./logs.component.scss'],
  imports: [
    CommonModule,
    PageHeaderComponent,
    NgbNavModule,
    FormsModule,
    ReactiveFormsModule,
    ScrollingModule,
  ],
})
export class LogsComponent
  extends LoadingComponentWithPermissions
  implements OnInit, AfterViewInit, OnDestroy
{
  private logService = inject(LogService)
  private changedetectorRef = inject(ChangeDetectorRef)

  public logs: Array<{ message: string; level: number }> = []

  public logFiles: string[] = []

  public activeLog: string

  public autoRefreshEnabled: boolean = true
  public autoRefreshInterval: number = 30
  public isLoadingMore: boolean = false

  private currentOffset: number = 0
  private readonly pageSize: number = 5000
  private hasMoreLogs: boolean = true
  private wasAtBottom: boolean = true

  @ViewChild('logContainer') logContainer: CdkVirtualScrollViewport

  ngOnInit(): void {
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
        timer(this.autoRefreshInterval * 1000, this.autoRefreshInterval * 1000)
          .pipe(
            filter(() => this.autoRefreshEnabled),
            takeUntil(this.unsubscribeNotifier)
          )
          .subscribe(() => {
            this.reloadLogs(true)
          })
      })
  }

  ngAfterViewInit(): void {
    if (this.logContainer) {
      this.logContainer.scrolledIndexChange
        .pipe(takeUntil(this.unsubscribeNotifier))
        .subscribe((index) => {
          const maxIndex = this.logs.length - 1
          this.wasAtBottom = index >= maxIndex - 50

          if (index < 100 && !this.isLoadingMore && this.hasMoreLogs) {
            this.loadMoreLogs()
          }
        })
    }
  }

  ngOnDestroy(): void {
    super.ngOnDestroy()
  }

  reloadLogs(isAutoRefresh: boolean = false): void {
    if (!isAutoRefresh) {
      this.loading = true
    }
    this.currentOffset = 0
    this.hasMoreLogs = true
    this.isLoadingMore = false

    this.logService
      .get(this.activeLog, { tail: this.pageSize })
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: (result) => {
          this.logs = this.parseLogsWithLevel(result)
          this.currentOffset = result.length
          this.hasMoreLogs = result.length === this.pageSize
          this.loading = false

          if (!isAutoRefresh || this.wasAtBottom) {
            this.scrollToBottom()
          }
        },
        error: (error) => {
          console.error('Error loading logs:', error)
          this.logs = []
          this.loading = false
          this.hasMoreLogs = false
        },
      })
  }

  loadMoreLogs(): void {
    if (this.isLoadingMore || !this.hasMoreLogs) {
      return
    }

    this.isLoadingMore = true
    const newOffset = this.currentOffset + this.pageSize

    const currentIndex = this.logContainer?.measureScrollOffset('top')
      ? Math.floor(this.logContainer.measureScrollOffset('top') / 20)
      : 0

    this.logService
      .get(this.activeLog, { tail: newOffset })
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: (result) => {
          if (result.length > this.logs.length) {
            const newLogsCount = result.length - this.logs.length
            const newLogs = result.slice(0, newLogsCount)
            this.logs = [...this.parseLogsWithLevel(newLogs), ...this.logs]
            this.currentOffset = result.length
            this.hasMoreLogs = result.length >= newOffset

            this.changedetectorRef.detectChanges()
            if (this.logContainer) {
              const newIndex = currentIndex + newLogsCount
              this.logContainer.scrollToIndex(newIndex)
            }
          } else {
            this.hasMoreLogs = false
          }
          this.isLoadingMore = false
        },
        error: (error) => {
          console.error('Error loading more logs:', error)
          this.isLoadingMore = false
          this.hasMoreLogs = false
        },
      })
  }

  getLogLevel(log: string): number {
    if (log.includes('[DEBUG]')) {
      return 10
    } else if (log.includes('[WARNING]')) {
      return 30
    } else if (log.includes('[ERROR]')) {
      return 40
    } else if (log.includes('[CRITICAL]')) {
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

  trackByIndex(index: number): number {
    return index
  }

  scrollToBottom(): void {
    this.changedetectorRef.detectChanges()
    if (this.logContainer?.elementRef?.nativeElement) {
      try {
        this.logContainer.scrollToIndex(this.logs.length - 1)
      } catch (e) {
        console.warn('Unable to scroll to bottom:', e)
      }
    }
  }
}
