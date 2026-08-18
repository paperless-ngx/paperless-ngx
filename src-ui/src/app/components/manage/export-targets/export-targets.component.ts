import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgbDropdownModule, NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subject, first, takeUntil, tap } from 'rxjs'
import {
  EXPORT_TARGET_KINDS,
  ExportTarget,
  ExportTargetKind,
} from 'src/app/data/export-target'
import { ObjectWithPermissions } from 'src/app/data/object-with-permissions'
import { IfOwnerDirective } from 'src/app/directives/if-owner.directive'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import {
  PermissionAction,
  PermissionsService,
} from 'src/app/services/permissions.service'
import { ExportTargetService } from 'src/app/services/rest/export-target.service'
import { ToastService } from 'src/app/services/toast.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { EditDialogMode } from '../../common/edit-dialog/edit-dialog.component'
import { ExportTargetEditDialogComponent } from '../../common/edit-dialog/export-target-edit-dialog/export-target-edit-dialog.component'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { PermissionsDialogComponent } from '../../common/permissions-dialog/permissions-dialog.component'
import { ComponentWithPermissions } from '../../with-permissions/with-permissions.component'

@Component({
  selector: 'pngx-export-targets',
  templateUrl: './export-targets.component.html',
  styleUrls: ['./export-targets.component.scss'],
  imports: [
    PageHeaderComponent,
    IfPermissionsDirective,
    IfOwnerDirective,
    FormsModule,
    ReactiveFormsModule,
    NgbDropdownModule,
    NgxBootstrapIconsModule,
  ],
})
export class ExportTargetsComponent
  extends ComponentWithPermissions
  implements OnInit, OnDestroy
{
  private readonly exportTargetService = inject(ExportTargetService)
  private toastService = inject(ToastService)
  private modalService = inject(NgbModal)
  permissionsService = inject(PermissionsService)

  readonly exportTargets = signal<ExportTarget[]>([])
  readonly loading = signal(true)
  readonly show = signal(false)

  unsubscribeNotifier: Subject<any> = new Subject()

  ngOnInit(): void {
    this.reload()
  }

  ngOnDestroy() {
    this.unsubscribeNotifier.next(true)
  }

  private reload() {
    this.exportTargetService
      .listAll(null, null, { full_perms: true })
      .pipe(
        first(),
        takeUntil(this.unsubscribeNotifier),
        tap((r) => {
          this.exportTargets.set(r.results)
          this.loading.set(false)
          this.show.set(true)
        })
      )
      .subscribe({
        error: (e) => {
          this.loading.set(false)
          this.toastService.showError(
            $localize`Error retrieving export targets`,
            e
          )
        },
      })
  }

  kindName(target: ExportTarget): string {
    return (
      EXPORT_TARGET_KINDS.find((kind) => kind.id === target.kind)?.name ??
      target.kind
    )
  }

  kindIcon(target: ExportTarget): string {
    return EXPORT_TARGET_KINDS.find((kind) => kind.id === target.kind)?.icon
  }

  destination(target: ExportTarget): string {
    switch (target.kind) {
      case ExportTargetKind.S3:
        return target.config?.prefix
          ? `${target.config?.bucket}/${target.config.prefix}`
          : (target.config?.bucket ?? '')
      case ExportTargetKind.SFTP:
        return `${target.config?.host ?? ''}:${target.config?.path ?? ''}`
      case ExportTargetKind.Local:
        return target.config?.path ?? ''
      default:
        return ''
    }
  }

  editTarget(target: ExportTarget = null) {
    const modal = this.modalService.open(ExportTargetEditDialogComponent, {
      backdrop: 'static',
      size: 'xl',
    })
    modal.componentInstance.dialogMode.set(
      target ? EditDialogMode.EDIT : EditDialogMode.CREATE
    )
    modal.componentInstance.object = target
    modal.componentInstance.succeeded
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((newTarget) => {
        this.toastService.showInfo(
          $localize`Saved export target "${newTarget.name}".`
        )
        this.exportTargetService.clearCache()
        this.reload()
      })
    modal.componentInstance.failed
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((e) => {
        this.toastService.showError($localize`Error saving export target.`, e)
      })
  }

  deleteTarget(target: ExportTarget) {
    const modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Confirm delete export target`
    modal.componentInstance.messageBold = $localize`This operation will permanently delete this export target.`
    modal.componentInstance.message = $localize`Documents already delivered to the destination are not affected. This operation cannot be undone.`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Proceed`
    modal.componentInstance.confirmClicked.subscribe(() => {
      modal.componentInstance.buttonsEnabled.set(false)
      this.exportTargetService.delete(target).subscribe({
        next: () => {
          modal.close()
          this.toastService.showInfo(
            $localize`Deleted export target "${target.name}"`
          )
          this.exportTargetService.clearCache()
          this.reload()
        },
        error: (e) => {
          this.toastService.showError(
            $localize`Error deleting export target "${target.name}".`,
            e
          )
        },
      })
    })
  }

  editPermissions(target: ExportTarget) {
    const modal = this.modalService.open(PermissionsDialogComponent, {
      backdrop: 'static',
    })
    const dialog: PermissionsDialogComponent =
      modal.componentInstance as PermissionsDialogComponent
    dialog.object = target
    modal.componentInstance.confirmClicked.subscribe(
      ({ permissions, merge }) => {
        modal.componentInstance.buttonsEnabled.set(false)
        target.owner = permissions['owner']
        target['set_permissions'] = permissions['set_permissions']
        this.exportTargetService.patch(target).subscribe({
          next: () => {
            this.toastService.showInfo($localize`Permissions updated`)
            modal.close()
          },
          error: (e) => {
            this.toastService.showError(
              $localize`Error updating permissions`,
              e
            )
          },
        })
      }
    )
  }

  userCanEdit(obj: ObjectWithPermissions): boolean {
    return this.permissionsService.currentUserHasObjectPermissions(
      PermissionAction.Change,
      obj
    )
  }

  userIsOwner(obj: ObjectWithPermissions): boolean {
    return this.permissionsService.currentUserOwnsObject(obj)
  }
}
