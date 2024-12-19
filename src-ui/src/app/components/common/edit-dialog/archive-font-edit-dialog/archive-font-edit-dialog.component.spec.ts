// import { HttpClientTestingModule } from '@angular/common/http/testing'
// import { ComponentFixture, TestBed } from '@angular/core/testing'
// import { FormsModule, ReactiveFormsModule } from '@angular/forms'
// import { NgbActiveModal, NgbModule } from '@ng-bootstrap/ng-bootstrap'
// import { NgSelectModule } from '@ng-select/ng-select'
// import { IfOwnerDirective } from 'src/app/directives/if-owner.directive'
// import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
// import { SettingsService } from 'src/app/services/settings.service'
// import { CheckComponent } from '../../input/check/check.component'
// import { ColorComponent } from '../../input/color/color.component'
// import { PermissionsFormComponent } from '../../input/permissions/permissions-form/permissions-form.component'
// import { SelectComponent } from '../../input/select/select.component'
// import { TextComponent } from '../../input/text/text.component'
// import { EditDialogMode } from '../edit-dialog.component'
// import { FontLanguageEditDialogComponent } from './font-language-edit-dialog.component'
// import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
//
// describe('TagEditDialogComponent', () => {
//   let component: FontLanguageEditDialogComponent
//   let settingsService: SettingsService
//   let fixture: ComponentFixture<FontLanguageEditDialogComponent>
//
//   beforeEach(async () => {
//     TestBed.configureTestingModule({
//       declarations: [
//         FontLanguageEditDialogComponent,
//         IfPermissionsDirective,
//         IfOwnerDirective,
//         SelectComponent,
//         TextComponent,
//         PermissionsFormComponent,
//         ColorComponent,
//         CheckComponent,
//       ],
//       providers: [NgbActiveModal, SettingsService],
//       imports: [
//         HttpClientTestingModule,
//         FormsModule,
//         ReactiveFormsModule,
//         NgSelectModule,
//         NgbModule,
//         NgxBootstrapIconsModule.pick(allIcons),
//       ],
//     }).compileComponents()
//
//     fixture = TestBed.createComponent(FontLanguageEditDialogComponent)
//     settingsService = TestBed.inject(SettingsService)
//     settingsService.currentUser = { id: 99, username: 'user99' }
//     component = fixture.componentInstance
//
//     fixture.detectChanges()
//   })
//
//   it('should support create and edit modes', () => {
//     component.dialogMode = EditDialogMode.CREATE
//     const createTitleSpy = jest.spyOn(component, 'getCreateTitle')
//     const editTitleSpy = jest.spyOn(component, 'getEditTitle')
//     fixture.detectChanges()
//     expect(createTitleSpy).toHaveBeenCalled()
//     expect(editTitleSpy).not.toHaveBeenCalled()
//     component.dialogMode = EditDialogMode.EDIT
//     fixture.detectChanges()
//     expect(editTitleSpy).toHaveBeenCalled()
//   })
// })
