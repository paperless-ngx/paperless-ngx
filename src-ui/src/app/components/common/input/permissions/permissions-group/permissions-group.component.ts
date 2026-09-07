import { Component, forwardRef, inject } from '@angular/core'
import { toSignal } from '@angular/core/rxjs-interop'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgSelectComponent } from '@ng-select/ng-select'
import { catchError, map, of } from 'rxjs'
import { Group } from 'src/app/data/group'
import { GroupService } from 'src/app/services/rest/group.service'
import { ToastService } from 'src/app/services/toast.service'
import { AbstractInputComponent } from '../../abstract-input'

@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => PermissionsGroupComponent),
      multi: true,
    },
  ],
  selector: 'pngx-permissions-group',
  templateUrl: './permissions-group.component.html',
  styleUrls: ['./permissions-group.component.scss'],
  imports: [NgSelectComponent, FormsModule, ReactiveFormsModule],
})
export class PermissionsGroupComponent extends AbstractInputComponent<Group> {
  private readonly groupService = inject(GroupService)
  private readonly toastService = inject(ToastService)
  readonly groups = toSignal(
    this.groupService.listAll().pipe(
      map((result) => result.results),
      catchError((error) => {
        this.toastService.showError($localize`Error retrieving groups`, error)
        return of([])
      })
    ),
    { initialValue: undefined as Group[] }
  )
}
