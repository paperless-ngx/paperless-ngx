import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { By } from '@angular/platform-browser'
import { RouterModule } from '@angular/router'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { routes } from 'src/app/app-routing.module'
import { LogoComponent } from '../common/logo/logo.component'
import { NotFoundComponent } from './not-found.component'

describe('NotFoundComponent', () => {
  let component: NotFoundComponent
  let fixture: ComponentFixture<NotFoundComponent>

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [
        NgxBootstrapIconsModule.pick(allIcons),
        NotFoundComponent,
        LogoComponent,
        RouterModule.forRoot(routes),
      ],
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
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
