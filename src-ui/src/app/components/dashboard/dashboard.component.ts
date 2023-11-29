import { Component } from '@angular/core'
import { SavedViewService } from 'src/app/services/rest/saved-view.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ComponentWithPermissions } from '../with-permissions/with-permissions.component'
import { TourService } from 'ngx-ui-tour-ng-bootstrap'
import { PaperlessSavedView } from 'src/app/data/paperless-saved-view'
import { ToastService } from 'src/app/services/toast.service'
import { SETTINGS_KEYS } from 'src/app/data/paperless-uisettings'
import {
  CdkDragDrop,
  CdkDragEnd,
  CdkDragStart,
  moveItemInArray,
} from '@angular/cdk/drag-drop'

@Component({
  selector: 'pngx-dashboard',
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.scss'],
})
export class DashboardComponent extends ComponentWithPermissions {
  public dashboardViews: PaperlessSavedView[] = []
  constructor(
    public settingsService: SettingsService,
    public savedViewService: SavedViewService,
    private tourService: TourService,
    private toastService: ToastService
  ) {
    super()

    this.savedViewService.listAll().subscribe(() => {
      this.dashboardViews = this.savedViewService.dashboardViews
    })
  }

  get subtitle() {
    if (this.settingsService.displayName) {
      return $localize`Hello ${this.settingsService.displayName}, welcome to Paperless-ngx`
    } else {
      return $localize`Welcome to Paperless-ngx`
    }
  }

  completeTour() {
    if (this.tourService.getStatus() !== 0) {
      this.tourService.end() // will call settingsService.completeTour()
    } else {
      this.settingsService.completeTour()
    }
  }

  onDragStart(event: CdkDragStart) {
    this.settingsService.globalDropzoneEnabled = false
  }

  onDragEnd(event: CdkDragEnd) {
    this.settingsService.globalDropzoneEnabled = true
  }

  onDrop(event: CdkDragDrop<PaperlessSavedView[]>) {
    moveItemInArray(
      this.dashboardViews,
      event.previousIndex,
      event.currentIndex
    )

    this.settingsService
      .updateDashboardViewsSort(this.dashboardViews)
      .subscribe({
        next: () => {
          this.toastService.showInfo($localize`Dashboard updated`)
        },
        error: (e) => {
          this.toastService.showError($localize`Error updating dashboard`, e)
        },
      })
  }
}
