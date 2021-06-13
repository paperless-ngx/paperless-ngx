import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { combineLatest, Observable } from 'rxjs';
import { tap } from 'rxjs/operators';
import { PaperlessSavedView } from 'src/app/data/paperless-saved-view';
import { AbstractPaperlessService } from './abstract-paperless-service';

@Injectable({
  providedIn: 'root'
})
export class SavedViewService extends AbstractPaperlessService<PaperlessSavedView> {

  constructor(http: HttpClient) {
    super(http, 'saved_views')
    this.reload()
  }

  private reload() {
    this.listAll().subscribe(r => this.savedViews = r.results)
  }

  private savedViews: PaperlessSavedView[] = []

  get allViews() {
    return this.savedViews
  }

  get sidebarViews() {
    return this.savedViews.filter(v => v.show_in_sidebar)
  }

  get dashboardViews() {
    return this.savedViews.filter(v => v.show_on_dashboard)
  }

  create(o: PaperlessSavedView) {
    return super.create(o).pipe(
      tap(() => this.reload())
    )
  }

  update(o: PaperlessSavedView) {
    return super.update(o).pipe(
      tap(() => this.reload())
    )
  }

  patchMany(objects: PaperlessSavedView[]): Observable<PaperlessSavedView[]> {
    return combineLatest(objects.map(o => super.patch(o))).pipe(
      tap(() => this.reload())
    )
  }

  delete(o: PaperlessSavedView) {
    return super.delete(o).pipe(
      tap(() => this.reload())
    )
  }
}
