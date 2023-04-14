import "./Input.scss"

const Input = (props) => {

    if(props.type === "select"){

        return (

            <div>

            </div>

        )
    }

    if(props.type === "input-text"){

        return (

            <div className="input-text">
                <label>{props.label}</label>
                <input placeholder={props.placeholder}/>
            </div>
        )
    }
        
}
export default Input;