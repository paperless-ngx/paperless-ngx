import { ComponentFixture, TestBed } from '@angular/core/testing'

import { ConfigComponent } from './config.component'
import { ConfigService } from 'src/app/services/config.service'
import { ToastService } from 'src/app/services/toast.service'
import { of, throwError } from 'rxjs'
import { OutputTypeConfig } from 'src/app/data/paperless-config'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { BrowserModule } from '@angular/platform-browser'
import { NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { NgSelectModule } from '@ng-select/ng-select'
import { TextComponent } from '../../common/input/text/text.component'
import { NumberComponent } from '../../common/input/number/number.component'
import { SwitchComponent } from '../../common/input/switch/switch.component'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { SelectComponent } from '../../common/input/select/select.component'
import { FileComponent } from '../../common/input/file/file.component'
import { SettingsService } from 'src/app/services/settings.service'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'

describe('ConfigComponent', () => {
  let component: ConfigComponent
  let fixture: ComponentFixture<ConfigComponent>
  let configService: ConfigService
  let toastService: ToastService
  let settingService: SettingsService

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [
        ConfigComponent,
        TextComponent,
        SelectComponent,
        NumberComponent,
        SwitchComponent,
        FileComponent,
        PageHeaderComponent,
      ],
      imports: [
        BrowserModule,
        NgbModule,
        NgSelectModule,
        FormsModule,
        ReactiveFormsModule,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    configService = TestBed.inject(ConfigService)
    toastService = TestBed.inject(ToastService)
    settingService = TestBed.inject(SettingsService)
    fixture = TestBed.createComponent(ConfigComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should load config on init, show error if necessary', () => {
    const getSpy = jest.spyOn(configService, 'getConfig')
    const errorSpy = jest.spyOn(toastService, 'showError')
    getSpy.mockReturnValueOnce(
      throwError(() => new Error('Error getting config'))
    )
    component.ngOnInit()
    expect(getSpy).toHaveBeenCalled()
    expect(errorSpy).toHaveBeenCalled()
    getSpy.mockReturnValueOnce(
      of({ output_type: OutputTypeConfig.PDF_A } as any)
    )
    component.ngOnInit()
    expect(component.initialConfig).toEqual({
      output_type: OutputTypeConfig.PDF_A,
    })
  })

  it('should save config, show error if necessary', () => {
    const saveSpy = jest.spyOn(configService, 'saveConfig')
    const errorSpy = jest.spyOn(toastService, 'showError')
    saveSpy.mockReturnValueOnce(
      throwError(() => new Error('Error saving config'))
    )
    component.saveConfig()
    expect(saveSpy).toHaveBeenCalled()
    expect(errorSpy).toHaveBeenCalled()
    saveSpy.mockReturnValueOnce(
      of({ output_type: OutputTypeConfig.PDF_A } as any)
    )
    component.saveConfig()
    expect(component.initialConfig).toEqual({
      output_type: OutputTypeConfig.PDF_A,
    })
  })

  it('should support discard changes', () => {
    component.initialConfig = { output_type: OutputTypeConfig.PDF_A2 } as any
    component.configForm.patchValue({ output_type: OutputTypeConfig.PDF_A })
    component.discardChanges()
    expect(component.configForm.get('output_type').value).toEqual(
      OutputTypeConfig.PDF_A2
    )
  })

  it('should support JSON validation for e.g. user_args', () => {
    component.configForm.patchValue({ user_args: '{ foo bar }' })
    expect(component.errors).toEqual({ user_args: 'Invalid JSON' })
    component.configForm.patchValue({ user_args: '{ "foo": "bar" }' })
    expect(component.errors).toEqual({ user_args: null })
  })

  it('should upload file, show error if necessary', () => {
    const uploadSpy = jest.spyOn(configService, 'uploadFile')
    const errorSpy = jest.spyOn(toastService, 'showError')
    uploadSpy.mockReturnValueOnce(
      throwError(() => new Error('Error uploading file'))
    )
    component.uploadFile(new File([], 'test.png'), 'app_logo')
    expect(uploadSpy).toHaveBeenCalled()
    expect(errorSpy).toHaveBeenCalled()
    uploadSpy.mockReturnValueOnce(
      of({ app_logo: 'https://example.com/logo/test.png' } as any)
    )
    component.uploadFile(new File([], 'test.png'), 'app_logo')
    expect(component.initialConfig).toEqual({
      app_logo: 'https://example.com/logo/test.png',
    })
  })

  it('should refresh ui settings after save or upload', () => {
    const saveSpy = jest.spyOn(configService, 'saveConfig')
    const initSpy = jest.spyOn(settingService, 'initializeSettings')
    saveSpy.mockReturnValueOnce(
      of({ output_type: OutputTypeConfig.PDF_A } as any)
    )
    component.saveConfig()
    expect(initSpy).toHaveBeenCalled()

    const uploadSpy = jest.spyOn(configService, 'uploadFile')
    uploadSpy.mockReturnValueOnce(
      of({ app_logo: 'https://example.com/logo/test.png' } as any)
    )
    component.uploadFile(new File([], 'test.png'), 'app_logo')
    expect(initSpy).toHaveBeenCalled()
  })
})
