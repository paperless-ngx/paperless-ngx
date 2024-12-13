import { DatePipe } from '@angular/common'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { By } from '@angular/platform-browser'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { of, throwError } from 'rxjs'
import { DocumentNote } from 'src/app/data/document-note'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { PermissionsService } from 'src/app/services/permissions.service'
import { DocumentNotesService } from 'src/app/services/rest/document-notes.service'
import { UserService } from 'src/app/services/rest/user.service'
import { ToastService } from 'src/app/services/toast.service'
import { DocumentNotesComponent } from './document-notes.component'

const notes: DocumentNote[] = [
  {
    id: 23,
    note: 'Note 23',
    user: {
      id: 1,
      username: 'user1',
      first_name: 'User1',
      last_name: 'Lastname1',
    },
  },
  {
    id: 24,
    note: 'Note 24',
    user: {
      id: 1,
      username: 'user1',
      first_name: 'User1',
      last_name: 'Lastname1',
    },
  },
  {
    id: 25,
    note: 'Note 25',
    user: { id: 2, username: 'user2' },
  },
  {
    id: 30,
    note: 'Note 30',
    user: { id: 3, username: 'user3' },
  },
]

describe('DocumentNotesComponent', () => {
  let component: DocumentNotesComponent
  let fixture: ComponentFixture<DocumentNotesComponent>
  let notesService: DocumentNotesService
  let toastService: ToastService

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [
        DocumentNotesComponent,
        CustomDatePipe,
        IfPermissionsDirective,
      ],
      imports: [
        FormsModule,
        ReactiveFormsModule,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
      providers: [
        {
          provide: UserService,
          useValue: {
            listAll: () =>
              of({
                results: [
                  {
                    id: 1,
                    username: 'user1',
                    first_name: 'User1',
                    last_name: 'Lastname1',
                  },
                  {
                    id: 2,
                    username: 'user2',
                  },
                  {
                    id: 3,
                    username: 'user3',
                  },
                ],
              }),
          },
        },
        {
          provide: PermissionsService,
          useValue: {
            currentUserCan: () => true,
          },
        },
        CustomDatePipe,
        DatePipe,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    notesService = TestBed.inject(DocumentNotesService)
    toastService = TestBed.inject(ToastService)
    fixture = TestBed.createComponent(DocumentNotesComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should display notes with user name / username', () => {
    component.notes = notes
    fixture.detectChanges()
    expect(fixture.debugElement.nativeElement.textContent).toContain(
      notes[0].note
    )
    expect(fixture.debugElement.nativeElement.textContent).toContain(
      notes[1].note
    )
    expect(fixture.debugElement.nativeElement.textContent).toContain(
      notes[2].note
    )
    expect(fixture.debugElement.nativeElement.textContent).toContain(
      notes[3].note
    )
    expect(fixture.debugElement.nativeElement.textContent).toContain(
      'User1 Lastname1'
    )
    expect(fixture.debugElement.nativeElement.textContent).toContain('user2')
    expect(fixture.debugElement.nativeElement.textContent).toContain('user3')
  })

  it('should handle note user display in all situations', () => {
    expect(
      component.displayName({
        id: 1,
        user: {
          id: 1,
          username: 'user1',
          first_name: 'User1',
          last_name: 'Lastname1',
        },
      })
    ).toEqual('User1 Lastname1 (user1)')
    expect(
      component.displayName({ id: 1, user: { id: 2, username: 'user2' } })
    ).toEqual('user2')
    expect(component.displayName({ id: 1, user: 2 } as any)).toEqual('user2')
    expect(
      component.displayName({ id: 1, user: { id: 4, username: 'user4' } })
    ).toEqual('')
    expect(component.displayName({ id: 1 })).toEqual('')
  })

  it('should support note entry, show error if fails', () => {
    component.documentId = 12
    const note = 'This is the new note.'
    const noteTextArea = fixture.debugElement.query(By.css('textarea'))
    noteTextArea.nativeElement.value = note
    noteTextArea.nativeElement.dispatchEvent(new Event('input'))
    fixture.detectChanges()
    const addSpy = jest.spyOn(notesService, 'addNote')
    addSpy.mockReturnValueOnce(throwError(() => new Error('error saving note')))
    const toastsSpy = jest.spyOn(toastService, 'showError')
    const addButton = fixture.debugElement.query(By.css('button'))
    addButton.triggerEventHandler('click')
    expect(addSpy).toHaveBeenCalledWith(12, note)
    expect(toastsSpy).toHaveBeenCalled()

    addSpy.mockReturnValueOnce(
      of([...notes, { id: 31, note, user: { id: 1 } }])
    )
    addButton.triggerEventHandler('click')
    fixture.detectChanges()
    expect(fixture.debugElement.nativeElement.textContent).toContain(note)
  })

  it('should support note save on ctrl+Enter', () => {
    component.documentId = 12
    const note = 'This is the new note.'
    const noteTextArea = fixture.debugElement.query(By.css('textarea'))
    noteTextArea.nativeElement.value = note
    const addSpy = jest.spyOn(component, 'addNote')
    noteTextArea.nativeElement.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Enter', ctrlKey: true })
    )
    expect(addSpy).toHaveBeenCalled()
  })

  it('should support delete note, show error if fails', () => {
    component.documentId = 12
    component.notes = notes
    fixture.detectChanges()
    const deleteButton = fixture.debugElement.queryAll(By.css('button'))[1] // 0 is add button
    const deleteSpy = jest.spyOn(notesService, 'deleteNote')
    const toastsSpy = jest.spyOn(toastService, 'showError')
    deleteSpy.mockReturnValueOnce(
      throwError(() => new Error('error deleting note'))
    )
    deleteButton.triggerEventHandler('click')
    expect(deleteSpy).toHaveBeenCalledWith(12, notes[0].id)
    expect(toastsSpy).toHaveBeenCalled()
    fixture.detectChanges()
    expect(fixture.debugElement.nativeElement.textContent).toContain(
      notes[0].note
    )

    deleteSpy.mockReturnValueOnce(of(notes.slice(1, 2)))
    deleteButton.triggerEventHandler('click')
    expect(deleteSpy).toHaveBeenCalledWith(12, notes[0].id)
    fixture.detectChanges()
    expect(fixture.debugElement.nativeElement.textContent).not.toContain(
      notes[0].note
    )
  })
})
