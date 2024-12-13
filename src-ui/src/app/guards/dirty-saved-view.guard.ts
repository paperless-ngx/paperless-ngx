import { Injectable } from '@angular/core'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { first, Observable, Subject } from 'rxjs'
import { ConfirmDialogComponent } from '../components/common/confirm-dialog/confirm-dialog.component'
import { DocumentListComponent } from '../components/document-list/document-list.component'
import { SETTINGS_KEYS } from '../data/ui-settings'
import { SettingsService } from '../services/settings.service'

@Injectable()
export class DirtySavedViewGuard {
  constructor(
    private modalService: NgbModal,
    private settings: SettingsService
  ) {}

  canDeactivate(
    component: DocumentListComponent
  ): boolean | Observable<boolean> {
    return component.savedViewIsModified &&
      this.settings.get(SETTINGS_KEYS.SAVED_VIEWS_WARN_ON_UNSAVED_CHANGE)
      ? this.warn(component)
      : true
  }

  warn(component: DocumentListComponent) {
    let modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Unsaved Changes`
    modal.componentInstance.messageBold =
      $localize`You have unsaved changes to the saved view` +
      ' "' +
      component.getTitle()
    ;('".')
    modal.componentInstance.message = $localize`Are you sure you want to close this saved view?`
    modal.componentInstance.btnClass = 'btn-secondary'
    modal.componentInstance.btnCaption = $localize`Close`
    modal.componentInstance.alternativeBtnClass = 'btn-primary'
    modal.componentInstance.alternativeBtnCaption = $localize`Save and close`
    modal.componentInstance.alternativeClicked.pipe(first()).subscribe(() => {
      modal.componentInstance.buttonsEnabled = false
      component.saveViewConfig()
      modal.close()
    })
    modal.componentInstance.confirmClicked.pipe(first()).subscribe(() => {
      modal.componentInstance.buttonsEnabled = false
      modal.close()
    })

    const subject = new Subject<boolean>()
    modal.componentInstance.confirmSubject = subject
    modal.componentInstance.alternativeSubject = subject

    return subject
  }
}
