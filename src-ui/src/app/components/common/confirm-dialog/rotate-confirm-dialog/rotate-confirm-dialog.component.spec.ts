import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { SafeHtmlPipe } from 'src/app/pipes/safehtml.pipe'
import { RotateConfirmDialogComponent } from './rotate-confirm-dialog.component'

describe('RotateConfirmDialogComponent', () => {
  let component: RotateConfirmDialogComponent
  let fixture: ComponentFixture<RotateConfirmDialogComponent>

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [RotateConfirmDialogComponent, SafeHtmlPipe],
      imports: [NgxBootstrapIconsModule.pick(allIcons)],
      providers: [
        NgbActiveModal,
        SafeHtmlPipe,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(RotateConfirmDialogComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should support rotating the image', () => {
    component.documentID = 1
    fixture.detectChanges()
    component.rotate()
    fixture.detectChanges()
    expect(component.degrees).toBe(90)
    expect(fixture.nativeElement.querySelector('img').style.transform).toBe(
      'rotate(90deg)'
    )
    component.rotate()
    fixture.detectChanges()
    expect(fixture.nativeElement.querySelector('img').style.transform).toBe(
      'rotate(180deg)'
    )
  })

  it('should normalize degrees', () => {
    expect(component.degrees).toBe(0)
    component.rotate()
    expect(component.degrees).toBe(90)
    component.rotate()
    expect(component.degrees).toBe(180)
    component.rotate()
    expect(component.degrees).toBe(270)
    component.rotate()
    expect(component.degrees).toBe(0)
    component.rotate()
    expect(component.degrees).toBe(90)
    component.rotate(false)
    expect(component.degrees).toBe(0)
    component.rotate(false)
    expect(component.degrees).toBe(270)
  })
})
