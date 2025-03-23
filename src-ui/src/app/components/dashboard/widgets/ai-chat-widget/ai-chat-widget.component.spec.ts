import { ComponentFixture, TestBed } from '@angular/core/testing'

import { AiChatWidgetComponent } from './ai-chat-widget.component'

describe('AiChatWidgetComponent', () => {
  let component: AiChatWidgetComponent
  let fixture: ComponentFixture<AiChatWidgetComponent>

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [AiChatWidgetComponent],
    }).compileComponents()

    fixture = TestBed.createComponent(AiChatWidgetComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should create', () => {
    expect(component).toBeTruthy()
  })
})
