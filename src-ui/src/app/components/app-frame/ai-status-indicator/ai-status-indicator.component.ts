import { DatePipe } from '@angular/common'
import { Component, OnDestroy, OnInit, inject } from '@angular/core'
import { Router, RouterModule } from '@angular/router'
import {
  NgbPopoverModule,
  NgbTooltipModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subscription } from 'rxjs'
import { AIStatus } from 'src/app/data/ai-status'
import { AIStatusService } from 'src/app/services/ai-status.service'

@Component({
  selector: 'pngx-ai-status-indicator',
  standalone: true,
  templateUrl: './ai-status-indicator.component.html',
  styleUrls: ['./ai-status-indicator.component.scss'],
  imports: [
    DatePipe,
    NgbPopoverModule,
    NgbTooltipModule,
    NgxBootstrapIconsModule,
    RouterModule,
  ],
})
export class AIStatusIndicatorComponent implements OnInit, OnDestroy {
  private aiStatusService = inject(AIStatusService)
  private router = inject(Router)

  private subscription: Subscription

  public aiStatus: AIStatus = {
    active: false,
    processing: false,
    documents_scanned_today: 0,
    suggestions_applied: 0,
    pending_deletion_requests: 0,
  }

  ngOnInit(): void {
    this.subscription = this.aiStatusService
      .getStatus()
      .subscribe((status) => {
        this.aiStatus = status
      })
  }

  ngOnDestroy(): void {
    this.subscription?.unsubscribe()
  }

  /**
   * Get the appropriate icon name based on AI status
   */
  get iconName(): string {
    if (!this.aiStatus.active) {
      return 'robot' // Inactive
    }
    if (this.aiStatus.processing) {
      return 'robot' // Processing (will add animation via CSS)
    }
    return 'robot' // Active
  }

  /**
   * Get the CSS class for the icon based on status
   */
  get iconClass(): string {
    const classes = ['ai-status-icon']
    
    if (!this.aiStatus.active) {
      classes.push('inactive')
    } else if (this.aiStatus.processing) {
      classes.push('processing')
    } else {
      classes.push('active')
    }

    return classes.join(' ')
  }

  /**
   * Navigate to AI configuration settings
   */
  navigateToSettings(): void {
    this.router.navigate(['/settings'], { fragment: 'ai-scanner' })
  }

  /**
   * Check if there are any alerts (pending deletion requests)
   */
  get hasAlerts(): boolean {
    return this.aiStatus.pending_deletion_requests > 0
  }
}
