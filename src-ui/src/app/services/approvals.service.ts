import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Subject } from 'rxjs'
import { first, takeUntil } from 'rxjs/operators'
import {
  Approval,
  PaperlessApprovalStatus,
} from 'src/app/data/approval'
import { environment } from 'src/environments/environment'

@Injectable({
  providedIn: 'root',
})
export class ApprovalsService {
  private baseUrl: string = environment.apiBaseUrl

  public loading: boolean

  private approvals: PaperlessApproval[] = []

  private unsubscribeNotifer: Subject<any> = new Subject()

  public get total(): number {
    return this.approvals.length
  }

  public get allApprovals(): PaperlessApproval[] {
    return this.approvals.slice(0)
  }

  public get pendingApprovals(): PaperlessApproval[] {
    return this.approvals.filter((t) => t.status == PaperlessApprovalStatus.Pending)
  }

  public get successApprovals(): PaperlessApproval[] {
    return this.approvals.filter((t) => t.status == PaperlessApprovalStatus.Success)

  }

  public get failureApprovals(): PaperlessApproval[] {
    return this.approvals.filter(
      (t) => t.status == PaperlessApprovalStatus.Failure
    )
  }

  public get revokedApprovals(): PaperlessApproval[] {
    return this.approvals.filter((t) => t.status == PaperlessApprovalStatus.Revoked)
  }

  constructor(private http: HttpClient) {}

  public reload() {
    this.loading = true
    this.http
    .get<PaperlessApproval[]>(`${this.baseUrl}approvals/`)
    .pipe(takeUntil(this.unsubscribeNotifer), first())
    .subscribe((r) => {
      this.approvals = r // they're all  approvals, for now
      this.loading = false
    })
  }

  public updateApprovals(id: Set<number>,status: String) {
    this.http
      .post(`${this.baseUrl}update_approvals/`, {
        approvals: [...id],status: status
      })
      .pipe(takeUntil(this.unsubscribeNotifer), first())
      .subscribe((r) => {
        this.reload()
      })
  }

  public cancelPending(): void {
    this.unsubscribeNotifer.next(true)
  }
}
