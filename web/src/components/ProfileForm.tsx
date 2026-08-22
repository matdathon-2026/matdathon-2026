import React from 'react';
import type { Profile } from '../types';

interface Props {
  onSubmit: (profile: Profile) => void;
}

const REGIONS = ['서울','부산','대구','인천','광주','대전','울산','세종','경기','강원','충북','충남','전북','전남','경북','경남','제주','전국'];
const SITUATIONS = ['자립준비청년','보호연장아동','가정위탁 종료','잘 모르겠어요'];
const INTERESTS = ['생활','주거','교육','취업','의료','금융','심리'];
const HOUSING = ['월세','전세','자가','기숙사/시설','주거 불안정','잘 모르겠어요'];
const EMPLOYMENT = ['재학중','구직중','재직중','쉬고 있어요','잘 모르겠어요'];

export default function ProfileForm({ onSubmit }: Props) {
  const [age, setAge] = React.useState('');
  const [region, setRegion] = React.useState('서울');
  const [situation, setSituation] = React.useState('자립준비청년');
  const [interests, setInterests] = React.useState<string[]>([]);
  const [housingStatus, setHousingStatus] = React.useState('월세');
  const [employmentStatus, setEmploymentStatus] = React.useState('구직중');
  const [ageError, setAgeError] = React.useState('');

  function toggleInterest(v: string) {
    setInterests(prev => prev.includes(v) ? prev.filter(i => i !== v) : [...prev, v]);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const ageNum = parseInt(age, 10);
    if (!age || isNaN(ageNum) || ageNum < 15 || ageNum > 39) {
      setAgeError('만 나이를 15~39 사이로 입력해 주세요.');
      return;
    }
    setAgeError('');
    onSubmit({ age: ageNum, region, situation, interests, housingStatus, employmentStatus });
  }

  return (
    <form className="profile-form" onSubmit={handleSubmit} noValidate>
      <div className="form-group">
        <label htmlFor="age">만 나이 <span aria-hidden="true">*</span></label>
        <input
          id="age"
          type="number"
          inputMode="numeric"
          min={15}
          max={39}
          value={age}
          onChange={e => { setAge(e.target.value); setAgeError(''); }}
          placeholder="예: 21"
          aria-required="true"
          aria-describedby={ageError ? 'age-error' : undefined}
        />
        {ageError && <span id="age-error" role="alert" style={{ color: 'var(--color-error-text)', fontSize: '0.82rem' }}>{ageError}</span>}
      </div>

      <div className="form-group">
        <label htmlFor="region">지역</label>
        <select id="region" value={region} onChange={e => setRegion(e.target.value)}>
          {REGIONS.map(r => <option key={r} value={r}>{r}</option>)}
        </select>
      </div>

      <div className="form-group">
        <label htmlFor="situation">현재 상황</label>
        <select id="situation" value={situation} onChange={e => setSituation(e.target.value)}>
          {SITUATIONS.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      <div className="form-group">
        <span id="interests-label" style={{ fontWeight: 600, fontSize: '0.9rem' }}>관심 분야 (여러 개 선택 가능)</span>
        <div className="checkbox-group" role="group" aria-labelledby="interests-label">
          {INTERESTS.map(i => (
            <label key={i} className={`checkbox-label${interests.includes(i) ? ' checked' : ''}`}>
              <input
                type="checkbox"
                checked={interests.includes(i)}
                onChange={() => toggleInterest(i)}
                aria-label={i}
              />
              {i}
            </label>
          ))}
        </div>
      </div>

      <div className="form-group">
        <label htmlFor="housing">주거 현황</label>
        <select id="housing" value={housingStatus} onChange={e => setHousingStatus(e.target.value)}>
          {HOUSING.map(h => <option key={h} value={h}>{h}</option>)}
        </select>
      </div>

      <div className="form-group">
        <label htmlFor="employment">취업 현황</label>
        <select id="employment" value={employmentStatus} onChange={e => setEmploymentStatus(e.target.value)}>
          {EMPLOYMENT.map(em => <option key={em} value={em}>{em}</option>)}
        </select>
      </div>

      <button type="submit" className="btn-primary">🔍 나에게 맞는 지원사업 찾기</button>
    </form>
  );
}
