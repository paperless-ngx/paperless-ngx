import { Component, OnDestroy, OnInit } from '@angular/core'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { Subject, first, takeUntil } from 'rxjs'
import { Group } from 'src/app/data/group'
import { User } from 'src/app/data/user'
import { PermissionsService } from 'src/app/services/permissions.service'
import { GroupService } from 'src/app/services/rest/group.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { EditDialogMode } from '../../common/edit-dialog/edit-dialog.component'
import { GroupEditDialogComponent } from '../../common/edit-dialog/group-edit-dialog/group-edit-dialog.component'
import { UserEditDialogComponent } from '../../common/edit-dialog/user-edit-dialog/user-edit-dialog.component'
import { ComponentWithPermissions } from '../../with-permissions/with-permissions.component'

@Component({
  selector: 'pngx-users-groups',
  templateUrl: './users-groups.component.html',
  styleUrls: ['./users-groups.component.scss'],
})
export class UsersAndGroupsComponent
  extends ComponentWithPermissions
  implements OnInit, OnDestroy
{
  users: User[]
  groups: Group[]

  unsubscribeNotifier: Subject<any> = new Subject()

  constructor(
    private usersService: UserService,
    private groupsService: GroupService,
    private toastService: ToastService,
    private modalService: NgbModal,
    public permissionsService: PermissionsService,
    private settings: SettingsService
  ) {
    super()
  }

  ngOnInit(): void {
    this.usersService
      .listAll(null, null, { full_perms: true })
      .pipe(first(), takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: (r) => {
          this.users = r.results
        },
        error: (e) => {
          this.toastService.showError($localize`Error retrieving users`, e)
        },
      })

    this.groupsService
      .listAll(null, null, { full_perms: true })
      .pipe(first(), takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: (r) => {
          this.groups = r.results
        },
        error: (e) => {
          this.toastService.showError($localize`Error retrieving groups`, e)
        },
      })
  }

  ngOnDestroy() {
    this.unsubscribeNotifier.next(true)
  }

  editUser(user: User = null) {
    var modal = this.modalService.open(UserEditDialogComponent, {
      backdrop: 'static',
      size: 'xl',
    })
    modal.componentInstance.dialogMode = user
      ? EditDialogMode.EDIT
      : EditDialogMode.CREATE
    modal.componentInstance.object = user
    modal.componentInstance.succeeded
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((newUser: User) => {
        if (
          newUser.id === this.settings.currentUser.id &&
          (modal.componentInstance as UserEditDialogComponent).passwordIsSet
        ) {
          this.toastService.showInfo(
            $localize`Password has been changed, you will be logged out momentarily.`
          )
          setTimeout(() => {
            window.location.href = `${window.location.origin}/accounts/logout/?next=/accounts/login/?next=/`
          }, 2500)
        } else {
          this.toastService.showInfo(
            $localize`Saved user "${newUser.username}".`
          )
          this.usersService.listAll().subscribe((r) => {
            this.users = r.results
          })
        }
      })
    modal.componentInstance.failed
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((e) => {
        this.toastService.showError($localize`Error saving user.`, e)
      })
  }

  deleteUser(user: User) {
    let modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Confirm delete user account`
    modal.componentInstance.messageBold = $localize`This operation will permanently delete this user account.`
    modal.componentInstance.message = $localize`This operation cannot be undone.`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Proceed`
    modal.componentInstance.confirmClicked.subscribe(() => {
      modal.componentInstance.buttonsEnabled = false
      this.usersService.delete(user).subscribe({
        next: () => {
          modal.close()
          this.toastService.showInfo($localize`Deleted user`)
          this.usersService.listAll().subscribe((r) => {
            this.users = r.results
          })
        },
        error: (e) => {
          this.toastService.showError($localize`Error deleting user.`, e)
        },
      })
    })
  }

  editGroup(group: Group = null) {
    var modal = this.modalService.open(GroupEditDialogComponent, {
      backdrop: 'static',
      size: 'lg',
    })
    modal.componentInstance.dialogMode = group
      ? EditDialogMode.EDIT
      : EditDialogMode.CREATE
    modal.componentInstance.object = group
    modal.componentInstance.succeeded
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((newGroup) => {
        this.toastService.showInfo($localize`Saved group "${newGroup.name}".`)
        this.groupsService.listAll().subscribe((r) => {
          this.groups = r.results
        })
      })
    modal.componentInstance.failed
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((e) => {
        this.toastService.showError($localize`Error saving group.`, e)
      })
  }

  deleteGroup(group: Group) {
    let modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Confirm delete user group`
    modal.componentInstance.messageBold = $localize`This operation will permanently delete this user group.`
    modal.componentInstance.message = $localize`This operation cannot be undone.`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Proceed`
    modal.componentInstance.confirmClicked.subscribe(() => {
      modal.componentInstance.buttonsEnabled = false
      this.groupsService.delete(group).subscribe({
        next: () => {
          modal.close()
          this.toastService.showInfo($localize`Deleted group`)
          this.groupsService.listAll().subscribe((r) => {
            this.groups = r.results
          })
        },
        error: (e) => {
          this.toastService.showError($localize`Error deleting group.`, e)
        },
      })
    })
  }

  getGroupName(id: number): string {
    return this.groups?.find((g) => g.id === id)?.name ?? ''
  }
}
