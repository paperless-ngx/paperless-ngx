import { IsNumberPipe } from './is-number.pipe'

describe('IsNumberPipe', () => {
  it('should detect numbers', () => {
    const pipe = new IsNumberPipe()
    expect(pipe.transform(0)).toBeTruthy()
    expect(pipe.transform(123)).toBeTruthy()
    expect(pipe.transform('123')).toBeFalsy()
    expect(pipe.transform(null)).toBeFalsy()
    expect(pipe.transform(undefined)).toBeFalsy()
    expect(pipe.transform(NaN)).toBeFalsy()
  })
})
