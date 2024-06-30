import { Component, OnInit } from '@angular/core'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { Subject, takeUntil } from 'rxjs'
import { PermissionsService } from 'src/app/services/permissions.service'
import { FolderService } from 'src/app/services/rest/folder.service'
import { ToastService } from 'src/app/services/toast.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { FolderEditDialogComponent } from '../../common/edit-dialog/folder-edit-dialog/folder-edit-dialog.component'
import { EditDialogMode } from '../../common/edit-dialog/edit-dialog.component'
import { ComponentWithPermissions } from '../../with-permissions/with-permissions.component'
import { Folder } from 'src/app/data/folder'

@Component({
  selector: 'pngx-folders',
  templateUrl: './folder.component.html',
  styleUrls: ['./folder.component.scss'],
})
export class FoldersComponent
  extends ComponentWithPermissions
  implements OnInit
{
  public folders: Folder[] = []

  private unsubscribeNotifier: Subject<any> = new Subject()
  constructor(
    private folderService: FolderService,
    public permissionsService: PermissionsService,
    private modalService: NgbModal,
    private toastService: ToastService
  ) {
    super()
  }

  ngOnInit() {
    this.reload()
  }

  reload() {
    this.folderService
      .listAll()
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((r) => {
        this.folders = r.results
      })
  }

  editFolder(folder: Folder) {
    const modal = this.modalService.open(FolderEditDialogComponent)
    modal.componentInstance.dialogMode = folder
      ? EditDialogMode.EDIT
      : EditDialogMode.CREATE
    modal.componentInstance.object = folder
    modal.componentInstance.succeeded
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((newFolder) => {
        this.toastService.showInfo($localize`Saved folder "${newFolder.name}".`)
        this.folderService.clearCache()
        this.reload()
      })
    modal.componentInstance.failed
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((e) => {
        this.toastService.showError($localize`Error saving folder.`, e)
      })
  }

  deleteFolder(folder: Folder) {
    const modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Confirm delete folder`
    modal.componentInstance.messageBold = $localize`This operation will permanently delete this folder.`
    modal.componentInstance.message = $localize`This operation cannot be undone.`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Proceed`
    modal.componentInstance.confirmClicked.subscribe(() => {
      modal.componentInstance.buttonsEnabled = false
      this.folderService.delete(folder).subscribe({
        next: () => {
          modal.close()
          this.toastService.showInfo($localize`Deleted folder`)
          this.folderService.clearCache()
          this.reload()
        },
        error: (e) => {
          this.toastService.showError($localize`Error deleting folder.`, e)
        },
      })
    })
  }


}