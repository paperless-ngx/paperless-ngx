import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NotFoundComponent } from './not-found.component'
import { By } from '@angular/platform-browser'
import { LogoComponent } from '../common/logo/logo.component'
import { HttpClientTestingModule } from '@angular/common/http/testing'

describe('NotFoundComponent', () => {
  let component: NotFoundComponent
  let fixture: ComponentFixture<NotFoundComponent>

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [NotFoundComponent, LogoComponent],
      imports: [HttpClientTestingModule],
    }).compileComponents()

    fixture = TestBed.createComponent(NotFoundComponent)
    component = fixture.componentInstance

    fixture.detectChanges()
  })

  it('should create component', () => {
    expect(component).toBeTruthy()
    expect(fixture.nativeElement.textContent).toContain('Not Found')
    expect(fixture.debugElement.queryAll(By.css('a'))).toHaveLength(1)
  })
})
