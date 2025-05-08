import { HttpClient, HttpParams } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Observable, Subject } from 'rxjs'
import { first, takeUntil } from 'rxjs/operators'
import { Approval, ApprovalStatus } from 'src/app/data/approval'
import { environment } from 'src/environments/environment'
import { Results } from '../data/results'

@Injectable({
  providedIn: 'root',
})
export class ApprovalsService {
  private baseUrl: string = environment.apiBaseUrl

  public loading: boolean

  private approvals: Approval[] = []

  private unsubscribeNotifer: Subject<any> = new Subject()

  public get total(): number {
    return this.approvals.length
  }
  public getRevokedApprovals(page: number = 1): Observable<Results<Approval>> {
    const httpParams = new HttpParams().set('page', page.toString())
    return this.http.get<Results<Approval>>(`${environment.apiBaseUrl}approvals/?status__iexact=REVOKED`, {
      params: httpParams,
    })
  }

  public getPendingApprovals(page: number = 1): Observable<Results<Approval>> {
    const httpParams = new HttpParams().set('page', page.toString())
    return this.http.get<Results<Approval>>(`${environment.apiBaseUrl}approvals/?status__iexact=PENDING`, {
      params: httpParams,
    })
  }

  public getSuccessApprovals(page: number = 1): Observable<Results<Approval>> {
    const httpParams = new HttpParams().set('page', page.toString())
    return this.http.get<Results<Approval>>(`${environment.apiBaseUrl}approvals/?status__iexact=SUCCESS`, {
      params: httpParams,
    })
  }

  public getFailureApprovals(page: number = 1): Observable<Results<Approval>> {
    const httpParams = new HttpParams().set('page', page.toString())
    return this.http.get<Results<Approval>>(`${environment.apiBaseUrl}approvals/?status__iexact=FAILURE`, {
      params: httpParams,
    })
  }

  public get allApprovals(): Approval[] {
    return this.approvals.slice(0)
  }

  public get pendingApprovals(): Approval[] {
    return this.approvals.filter((t) => t.status == ApprovalStatus.Pending)
  }

  public get successApprovals(): Approval[] {
    console.log(this.approvals)
    return this.approvals.filter((t) => t.status == ApprovalStatus.Success)

  }

  public get failureApprovals(): Approval[] {
    return this.approvals.filter(
      (t) => t.status == ApprovalStatus.Failure
    )
  }

  public get revokedApprovals(): Approval[] {
    return this.approvals.filter((t) => t.status == ApprovalStatus.Revoked)
  }

  constructor(private http: HttpClient) {}

  public reload() {
    this.loading = true
    this.http
    .get<Approval[]>(`${this.baseUrl}approvals/`)
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
        // this.reload()
      })
  }

  public cancelPending(): void {
    this.unsubscribeNotifer.next(true)
  }
}
