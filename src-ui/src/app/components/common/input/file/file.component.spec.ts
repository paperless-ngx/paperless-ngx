import { ComponentFixture, TestBed } from '@angular/core/testing'

import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { FileComponent } from './file.component'

describe('FileComponent', () => {
  let component: FileComponent
  let fixture: ComponentFixture<FileComponent>

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [FileComponent],
      imports: [FormsModule, ReactiveFormsModule],
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(FileComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should update file on change', () => {
    const event = { target: { files: [new File([], 'test.png')] } }
    component.onFile(event as any)
    expect(component.file.name).toEqual('test.png')
  })

  it('should get filename', () => {
    component.value = 'https://example.com:8000/logo/filename.svg'
    expect(component.filename).toEqual('filename.svg')
  })

  it('should fire upload event', () => {
    let firedFile
    component.file = new File([], 'test.png')
    component.upload.subscribe((file) => (firedFile = file))
    component.uploadClicked()
    expect(firedFile.name).toEqual('test.png')
    expect(component.file).toBeUndefined()
  })
})
