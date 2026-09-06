import { Component, forwardRef, inject } from '@angular/core'
import { toSignal } from '@angular/core/rxjs-interop'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgSelectComponent } from '@ng-select/ng-select'
import { map } from 'rxjs/operators'
import { Group } from 'src/app/data/group'
import { GroupService } from 'src/app/services/rest/group.service'
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
  readonly groups = toSignal(
    this.groupService.listAll().pipe(map((result) => result.results)),
    { initialValue: undefined as Group[] }
  )
}
